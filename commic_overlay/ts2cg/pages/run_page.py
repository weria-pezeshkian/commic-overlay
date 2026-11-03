"""RunPage: runs `ts2cg_bridge.pipeline`'s step list strictly in order.

Unlike CALM's own `run_page.py` (independent commands run in parallel via
`ParallelCommandRunner`), TS2CG's own pipeline is a dependency chain - each
step's output feeds the next - so this page runs exactly one step at a
time, in order, using the same `CommandRunner` for the subprocess steps
and running a `PythonStep`'s own callable directly in between.

A `SubprocessStep` whose `expected_outputs` are missing, even with exit code 0 (see
`pipeline.SubprocessStep`), fails the run immediately, the same as a nonzero exit code.
TS2CG's output depends on user-controlled settings (grid density, protein placement, wall
beads, ...) and can be degenerate under them, so the user decides whether to click Run again.
"""

from __future__ import annotations

import re

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...process_runner import CommandRunner
from ..ts2cg_bridge.pipeline import PythonStep, Step, SubprocessStep

_LINE_SPLIT = re.compile(r"[\r\n]")


class RunPage(QWidget):
    continue_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._runner = CommandRunner(self)
        self._runner.output_received.connect(self._on_output)
        self._runner.finished.connect(self._on_subprocess_finished)
        self._steps: list[Step] = []
        self._current_index = -1
        self._pending_output = ""
        self._cancelled = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Running")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        self._step_list = QListWidget()
        self._step_list.setMaximumHeight(180)
        layout.addWidget(self._step_list)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setTextVisible(False)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #555;")
        layout.addWidget(self._status_label)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        layout.addWidget(self._log_view, stretch=1)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self._on_cancel_clicked)
        buttons_row.addWidget(self._cancel_button)
        layout.addLayout(buttons_row)

    def refresh(self) -> None:
        pass

    def start(self, steps: list[Step]) -> None:
        self._steps = steps
        self._current_index = -1
        self._cancelled = False
        self._cancel_button.setEnabled(True)
        self._cancel_button.setText("Cancel")
        self._log_view.clear()
        self._step_list.clear()
        for step in steps:
            self._step_list.addItem(QListWidgetItem(f"○ {step.label}"))
        self._run_next_step()

    def _set_step_status(self, index: int, symbol: str) -> None:
        item = self._step_list.item(index)
        if item is not None:
            item.setText(f"{symbol} {self._steps[index].label}")

    def _run_next_step(self) -> None:
        if self._cancelled:
            return
        self._current_index += 1
        if self._current_index >= len(self._steps):
            self._on_all_steps_done()
            return

        self._run_current_step()

    def _run_current_step(self) -> None:
        step = self._steps[self._current_index]
        self._set_step_status(self._current_index, "●")
        self._status_label.setText(f"Running: {step.label}…")

        if isinstance(step, PythonStep):
            try:
                step.action()
            except Exception as exc:  # noqa: BLE001 - surfaced to the user, not a programming error
                self._on_step_failed(str(exc))
                return
            self._set_step_status(self._current_index, "✓")
            self._run_next_step()
            return

        self._pending_output = ""
        self._log_view.appendPlainText(f"\n--- {step.label} ---")
        self._runner.start(step.argv, step.cwd)

    def _on_output(self, text: str) -> None:
        self._pending_output += text
        *complete_lines, self._pending_output = _LINE_SPLIT.split(self._pending_output)
        for line in complete_lines:
            if line.strip():
                self._log_view.appendPlainText(line)

    def _on_subprocess_finished(self, exit_code: int) -> None:
        if self._pending_output.strip():
            self._log_view.appendPlainText(self._pending_output)
            self._pending_output = ""

        if self._runner.was_stopped():
            return

        step = self._steps[self._current_index]
        assert isinstance(step, SubprocessStep)

        if exit_code != 0:
            self._on_step_failed(f"exited with code {exit_code}")
            return

        if step.expected_outputs is not None and not all(p.exists() for p in step.expected_outputs):
            self._on_step_failed("reported success but didn't produce its expected output")
            return

        self._set_step_status(self._current_index, "✓")
        self._run_next_step()

    def _on_step_failed(self, reason: str) -> None:
        step = self._steps[self._current_index]
        self._set_step_status(self._current_index, "✗")
        self._status_label.setText(f"Failed: {step.label}")
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._cancel_button.setEnabled(False)
        QMessageBox.critical(self, "Run failed", f"{step.label} {reason}. See the log for details.")

    def _on_all_steps_done(self) -> None:
        self._status_label.setText("Done.")
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(1)
        self._cancel_button.setEnabled(False)
        self.continue_requested.emit()

    def _on_cancel_clicked(self) -> None:
        self._cancelled = True
        self._status_label.setText("Cancelling…")
        self._cancel_button.setEnabled(False)
        if self._runner.is_running():
            self._runner.stop()
