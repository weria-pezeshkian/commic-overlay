"""RunPage: shows a CALM run's live progress - one progress row per command (parsed from
CALM's own tqdm output), run concurrently if both `full` and `lipids` were selected."""

from __future__ import annotations

import re

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..calm_bridge.progress import parse_latest_progress
from ..calm_bridge.runner import ParallelCommandRunner

# Splits a chunk of subprocess output into individual visual lines - tqdm
# redraws its own bar in place via \r, not \n, so both have to be treated
# as line boundaries to catch each update (see calm_bridge/progress.py).
_LINE_SPLIT = re.compile(r"[\r\n]")


class _CommandProgressRow(QWidget):
    """One command's own progress bar, status text, and output log.

    Used once per command running on this page - two of these, side by
    side in time (not literally side by side on screen, stacked instead),
    is what makes `full` and `lipids` running concurrently show as two
    clearly separate, independently-updating indicators rather than one
    shared, ambiguous one.
    """

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pending_output = ""  # a line split across two output chunks, held until complete

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        header = QHBoxLayout()
        name_label = QLabel(label)
        name_label.setStyleSheet("font-weight: 600;")
        header.addWidget(name_label)
        self._status_label = QLabel("Running…")
        self._status_label.setStyleSheet("color: #666;")
        header.addWidget(self._status_label)
        header.addStretch(1)
        layout.addLayout(header)

        # Indeterminate (range 0,0 - Qt's own "busy" animation) until the
        # first real tqdm update is parsed from this command's own output
        # - CALM's own slower first phases (loading the structure,
        # building leaflets) report no per-step progress at all, so
        # there's genuinely nothing to show a real percentage for yet.
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setTextVisible(False)
        layout.addWidget(self._progress_bar)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumHeight(100)
        layout.addWidget(self._log_view)

    def reset(self) -> None:
        self._pending_output = ""
        self._log_view.clear()
        self._status_label.setText("Running…")
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setValue(0)

    def handle_output(self, text: str) -> None:
        self._pending_output += text
        *complete_lines, self._pending_output = _LINE_SPLIT.split(self._pending_output)
        for line in complete_lines:
            self._handle_line(line)

    def flush(self) -> None:
        """Processes whatever's left in the pending-line buffer - call once a command
        finishes, so a final line with no trailing \\r/\\n isn't silently dropped."""
        if self._pending_output.strip():
            self._handle_line(self._pending_output)
            self._pending_output = ""

    def _handle_line(self, line: str) -> None:
        progress = parse_latest_progress(line)
        if progress is not None:
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(progress.percent)
            label = progress.description or "Progress"
            self._status_label.setText(f"{label}: {progress.current}/{progress.total}")
            return
        if line.strip():
            self._log_view.appendPlainText(line)

    def set_finished(self, exit_code: int, stopped: bool) -> None:
        if stopped:
            self._status_label.setText("Cancelled.")
        elif exit_code != 0:
            self._status_label.setText("Failed.")
        else:
            self._status_label.setText("Done.")
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0 if stopped or exit_code != 0 else 1)
        if exit_code != 0 and not stopped:
            self._log_view.setVisible(True)


class RunPage(QWidget):
    """Owns the actual `ParallelCommandRunner` - `start()` is called by `MainWindow`
    right after navigating here from Parameters' own Continue (see app.py's
    `_on_parameters_run_requested` - Parameters always starts a genuinely fresh run,
    never just navigates back to a previous result). Advances to Results automatically
    once every command succeeds; stays here (showing the error, output expanded) if any
    one of them fails, so there's something to actually look at before going back to
    Parameters to retry.
    """

    continue_requested = Signal()  # emitted once every command finishes successfully

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._runner = ParallelCommandRunner(self)
        self._runner.output_received.connect(self._on_output)
        self._runner.all_finished.connect(self._on_all_finished)
        self._rows: list[_CommandProgressRow] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(20)

        self._rows_layout = QVBoxLayout()
        self._rows_layout.setSpacing(20)
        layout.addLayout(self._rows_layout)
        layout.addStretch(1)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.clicked.connect(self._on_cancel_clicked)
        buttons_row.addWidget(self._cancel_button)
        layout.addLayout(buttons_row)

    def refresh(self) -> None:
        pass

    def start(self, commands: list[tuple[str, list[str], str]]) -> None:
        """`commands`: (label, argv, cwd) tuples - one progress row is built per command,
        all started together (concurrently, if there's more than one)."""
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._rows = []

        for label, _argv, _cwd in commands:
            row = _CommandProgressRow(label)
            self._rows_layout.addWidget(row)
            self._rows.append(row)

        self._cancel_button.setEnabled(True)
        self._cancel_button.setText("Cancel")
        self._runner.start([(argv, cwd) for _label, argv, cwd in commands])

    def _on_output(self, index: int, text: str) -> None:
        self._rows[index].handle_output(text)

    def _on_cancel_clicked(self) -> None:
        for row in self._rows:
            row._status_label.setText("Cancelling…")
        self._cancel_button.setEnabled(False)
        self._runner.stop()

    def _on_all_finished(self, exit_codes: list[int]) -> None:
        stopped = self._runner.was_stopped()
        for row, exit_code in zip(self._rows, exit_codes, strict=True):
            row.flush()
            row.set_finished(exit_code, stopped)
        self._cancel_button.setEnabled(False)

        if stopped:
            return
        if any(code != 0 for code in exit_codes):
            QMessageBox.critical(
                self,
                "Run failed",
                "One of the CALM commands exited with an error — see the output log for details.",
            )
            return
        self.continue_requested.emit()
