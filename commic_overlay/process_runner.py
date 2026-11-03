"""Running an installed CLI tool's own subprocesses, tool-agnostically.

Every tool command this overlay drives is run as a genuine subprocess,
because a CLI entry point can call `sys.exit()` on its own error paths (both CALM's and
TS2CG's do), which would take this whole application down with it if
called directly (`CALM/gui/runner.py`'s own docstring notes the identical
reason for its Tkinter counterpart). `CommandRunner`/`ParallelCommandRunner`
know nothing about which tool's argv they're given - `calm/calm_bridge/
runner.py` and `ts2cg/ts2cg_bridge/runner.py` each own their own tool-
specific argv-building (`build_argv`) on top of this shared, tool-agnostic
process-running layer.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Signal


class CommandRunner(QObject):
    """Runs one CLI invocation as a `QProcess`, streaming merged stdout/stderr live.

    `QProcess`, not `subprocess.Popen`: progress reaches the GUI through
    Qt's own signal/slot system, on the main thread, with no manual
    polling thread or queue needed.

    `stop()` only ever signals this process itself, not a process group -
    this PySide6 build has no `QProcess.setChildProcessModifier` (added to
    Qt's own C++ API in 6.6, not yet exposed through these Python
    bindings) to put the child in its own session the way CALM's own
    Tkinter runner does (`start_new_session=True` + `os.killpg`), so a
    run's own worker subprocesses (e.g. CALM's own `--Workers N`) aren't
    killed along with it.
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
        # A Python-based CLI tool's own stdout switches from line-buffered
        # to fully block-buffered by default when writing to a pipe (not a
        # real terminal, which is exactly what this is) - output would
        # then only ever arrive in one lump at the very end instead of
        # live, confirmed directly against a real QProcess run. Forcing
        # PYTHONUNBUFFERED makes it arrive as the tool itself writes it.
        # Harmless for a non-Python (compiled) tool, which never reads it.
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
    """Runs a list of CLI invocations CONCURRENTLY, each its own `CommandRunner`.

    A separate `QProcess` per command, started together rather than one
    after another, so the user isn't waiting for one to finish before the
    other even starts.

    `output_received(index, text)` and `command_finished(index, exit_code)`
    both carry `index` - the command's own position in the list passed to
    `start()` - so a caller showing one progress indicator per command
    (see `calm/pages/run_page.py`) knows which one a given update belongs
    to.
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
