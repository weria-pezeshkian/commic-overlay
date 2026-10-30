"""WorkingDirPage: confirm/change the working directory, shared by every tool."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import settings
from ..theme import mark_primary


class WorkingDirPage(QWidget):
    """"Is <remembered>/current your working directory?" + Change/Continue.

    `current` (`Path.cwd()` at launch) is the fallback whenever there's no
    remembered directory yet (first run), or the remembered one no longer
    exists on disk. This directory seeds where every later file picker in
    the wizard starts browsing.
    """

    continue_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._directory: Path = Path.cwd()
        self._is_remembered = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        self._question_label = QLabel()
        self._question_label.setStyleSheet("font-size: 16px;")
        self._question_label.setWordWrap(True)
        layout.addWidget(self._question_label)

        path_row = QHBoxLayout()
        self._path_label = QLabel()
        self._path_label.setStyleSheet("font-size: 13px; color: #555;")
        self._path_label.setWordWrap(True)
        path_row.addWidget(self._path_label, stretch=1)
        change_button = QPushButton("Change")
        change_button.clicked.connect(self._on_change)
        path_row.addWidget(change_button)
        layout.addLayout(path_row)

        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        continue_button = QPushButton("Continue")
        mark_primary(continue_button)
        continue_button.clicked.connect(self._on_continue)
        buttons.addWidget(continue_button)
        layout.addLayout(buttons)

        self.refresh()

    def refresh(self) -> None:
        """Re-reads the remembered directory - call each time this page is shown."""
        remembered = settings.get_last_working_directory()
        if remembered is not None:
            self._directory = remembered
            self._is_remembered = True
        else:
            self._directory = Path.cwd()
            self._is_remembered = False
        self._update_labels()

    def _update_labels(self) -> None:
        kind = "previously most recently used" if self._is_remembered else "current"
        self._question_label.setText(f"Is this your working directory? ({kind})")
        self._path_label.setText(str(self._directory))

    def _on_change(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Select working directory", str(self._directory))
        if chosen:
            self._directory = Path(chosen)
            self._is_remembered = False
            self._update_labels()

    def _on_continue(self) -> None:
        settings.set_last_working_directory(self._directory)
        self.continue_requested.emit()

    def working_directory(self) -> Path:
        return self._directory
