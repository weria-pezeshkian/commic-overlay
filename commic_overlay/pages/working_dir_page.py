"""WorkingDirPage: confirm/change the working directory, shared by every tool."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import settings
from ..theme import mark_primary

DirectorySource = Literal["launch", "remembered", "home", "selected"]

_SOURCE_NOTES: dict[DirectorySource, str] = {
    "launch": "the directory the overlay was started from",
    "remembered": "previously most recently used",
    "home": "your home directory",
    "selected": "selected",
}


class WorkingDirPage(QWidget):
    """"Is this your working directory?" + Change/Continue.

    Offers `launch_directory` (the directory a shell started the overlay from) until
    Continue is clicked, then the remembered most recently used directory, then the
    home directory. This directory seeds where every later file picker in the wizard
    starts browsing.
    """

    continue_requested = Signal()

    def __init__(self, launch_directory: Path | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._launch_directory = launch_directory
        self._directory: Path = Path.home()
        self._source: DirectorySource = "home"

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
        """Re-reads the offered directory - call each time this page is shown."""
        remembered = settings.get_last_working_directory()
        if self._launch_directory is not None:
            self._directory, self._source = self._launch_directory, "launch"
        elif remembered is not None:
            self._directory, self._source = remembered, "remembered"
        else:
            self._directory, self._source = Path.home(), "home"
        self._update_labels()

    def _update_labels(self) -> None:
        self._question_label.setText(f"Is this your working directory? ({_SOURCE_NOTES[self._source]})")
        self._path_label.setText(str(self._directory))

    def _on_change(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Select working directory", str(self._directory))
        if chosen:
            self._directory, self._source = Path(chosen), "selected"
            self._update_labels()

    def _on_continue(self) -> None:
        settings.set_last_working_directory(self._directory)
        self._launch_directory = None
        self.continue_requested.emit()

    def working_directory(self) -> Path:
        return self._directory
