"""Building and launching real CALM CLI invocations.

Every CALM command is run as a genuine subprocess of the installed `CALM`
console script - never called in-process - because several of CALM's own
CLI entry points call `sys.exit()` on error, which would take this whole
application down with them if called directly (`CALM/gui/runner.py`'s own
docstring notes the identical reason for its Tkinter counterpart).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal

from .introspect import FieldSpec


def build_argv(argv_prefix: list[str], specs: list[FieldSpec], values: dict[str, object]) -> list[str]:
    """CALM's own argv, from one command's field specs and the Advanced window's current values.

    Same value-shape contract as CALM's own `CALM/gui/runner.py::build_argv`:
    a bool for "bool"/"bool_optional" fields, a list[str] for
    "multichoice"/"multi"/"append" fields, False/True/a non-empty str for
    "optional_flag_value" fields, a str for everything else. An
    empty/unset optional field is omitted from argv entirely - never
    passed as `--flag ""`.
    """
    argv = ["CALM", *argv_prefix]
    for spec in specs:
        value = values.get(spec.dest)
        if spec.kind == "bool":
            if value:
                argv.append(spec.flag)
        elif spec.kind == "bool_optional":
            long_name = spec.flag.lstrip("-")
            argv.append(f"--{long_name}" if value else f"--no-{long_name}")
        elif spec.kind in ("multichoice", "multi"):
            if value:
                assert isinstance(value, (list, tuple))
                argv.append(spec.flag)
                argv.extend(str(v) for v in value)
        elif spec.kind == "append":
            if value:
                assert isinstance(value, (list, tuple))
                for v in value:
                    argv.append(spec.flag)
                    argv.append(str(v))
        elif spec.kind == "optional_flag_value":
            if value is True:
                argv.append(spec.flag)
            elif isinstance(value, str) and value != "":
                argv.append(spec.flag)
                argv.append(value)
        else:
            if value is not None and str(value) != "":
                argv.append(spec.flag)
                argv.append(str(value))
    return argv


class CommandRunner(QObject):
    """Runs one CALM CLI invocation as a `QProcess`, streaming merged stdout/stderr live.

    `QProcess`, not `subprocess.Popen`: progress reaches the GUI through
    Qt's own signal/slot system, on the main thread, with no manual
    polling thread or queue needed.

    `stop()` only ever signals this process itself, not a process group -
    this PySide6 build has no `QProcess.setChildProcessModifier` (added to
    Qt's own C++ API in 6.6, not yet exposed through these Python
    bindings) to put the child in its own session the way CALM's own
    Tkinter runner does (`start_new_session=True` + `os.killpg`), so a
    `CALM analyze full --Workers N` run's own worker subprocesses aren't
    killed along with it if N > 1 - the wizard's own Run never sets
    `--Workers` above its default of 1, so this only matters for an
    Advanced-window run that raised it.
    """

    output_received = Signal(str)
    finished = Signal(int)  # exit code

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._process: QProcess | None = None
        self._stop_requested = False

    def is_running(self) -> bool:
        return self._process is not None and self._process.state() != QProcess.ProcessState.NotRunning

    def was_stopped(self) -> bool:
        """True if `stop()` was called for the most recent (or current) run."""
        return self._stop_requested

    def start(self, argv: list[str], cwd: str) -> None:
        if self.is_running():
            raise RuntimeError("A command is already running.")
        self._stop_requested = False
        process = QProcess(self)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.setWorkingDirectory(cwd)
        # CALM is a Python program; writing to a pipe (not a real terminal,
        # which is exactly what this is) makes Python's own stdout switch
        # from line-buffered to fully block-buffered by default, so output
        # would only ever arrive in one lump at the very end instead of
        # live - confirmed directly against a real QProcess run. Forcing
        # PYTHONUNBUFFERED makes it arrive as CALM itself writes it.
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(env)
        process.readyReadStandardOutput.connect(self._on_output_ready)
        process.finished.connect(self._on_finished)
        self._process = process
        process.start(argv[0], argv[1:])

    def _on_output_ready(self) -> None:
        assert self._process is not None
        data = self._process.readAllStandardOutput()
        text = bytes(data).decode("utf-8", errors="replace")
        if text:
            self.output_received.emit(text)

    def _on_finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self.finished.emit(exit_code)

    def stop(self) -> None:
        """Asks the running process to exit, escalating to a hard kill after 3s if it hasn't.

        Never blocks the calling (GUI) thread: `terminate()` is
        fire-and-forget, and the 3s escalation is a `QTimer`, not a
        blocking wait - the `finished` signal still fires normally,
        whenever the process actually exits, on its own time.
        """
        if self._process is None or not self.is_running():
            return
        self._stop_requested = True
        self._process.terminate()
        QTimer.singleShot(3000, self._kill_if_still_running)

    def _kill_if_still_running(self) -> None:
        if self._process is not None and self.is_running():
            self._process.kill()


class ParallelCommandRunner(QObject):
    """Runs a list of CALM CLI invocations CONCURRENTLY, each its own `CommandRunner`.

    Used when the wizard's Run needs to launch both `analyze full` and
    `analyze lipids` (both checked): a separate `QProcess` per command,
    started together rather than one after another, so the user isn't
    waiting for one to finish before the other even starts - each
    command's own `--Workers` is already sized for this (see
    `calm_bridge/system.py::default_worker_count`'s own `concurrent_jobs`,
    computed by whoever builds these commands) so the two don't together
    oversubscribe the machine.

    `output_received(index, text)` and `command_finished(index, exit_code)`
    both carry `index` - the command's own position in the list passed to
    `start()` - so a caller showing one progress indicator per command
    (see `pages/run_page.py`) knows which one a given update belongs to.
    """

    output_received = Signal(int, str)
    command_finished = Signal(int, int)  # command index, exit code
    all_finished = Signal(list)  # exit codes, in the same order commands were given

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._runners: list[CommandRunner] = []
        self._exit_codes: list[int | None] = []
        self._stop_requested = False

    def is_running(self) -> bool:
        return any(runner.is_running() for runner in self._runners)

    def was_stopped(self) -> bool:
        """True if `stop()` was called for the most recent (or current) run."""
        return self._stop_requested

    def start(self, commands: list[tuple[list[str], str]]) -> None:
        if self.is_running():
            raise RuntimeError("A command is already running.")
        self._stop_requested = False
        self._exit_codes = [None] * len(commands)
        self._runners = []
        for index, _ in enumerate(commands):
            runner = CommandRunner(self)
            runner.output_received.connect(lambda text, i=index: self.output_received.emit(i, text))
            runner.finished.connect(lambda code, i=index: self._on_command_finished(i, code))
            self._runners.append(runner)
        # Every runner constructed (and its signals connected) before any
        # of them is actually started, so a command that happens to finish
        # almost instantly can never fire its own finished signal before
        # a later command in the list has even been wired up.
        for runner, (argv, cwd) in zip(self._runners, commands, strict=True):
            runner.start(argv, cwd)

    def _on_command_finished(self, index: int, exit_code: int) -> None:
        self._exit_codes[index] = exit_code
        self.command_finished.emit(index, exit_code)
        if all(code is not None for code in self._exit_codes):
            self.all_finished.emit(list(self._exit_codes))

    def stop(self) -> None:
        self._stop_requested = True
        for runner in self._runners:
            runner.stop()
