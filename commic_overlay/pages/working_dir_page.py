"""WorkingDirPage: confirm/change the working directory, or load a saved config, shared by
every tool."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .. import settings
from ..theme import mark_primary
from ..widgets.config_dialogs import ask_config_load_path

DirectorySource = Literal["config", "config_folder", "launch", "remembered", "home", "selected"]

_SOURCE_NOTES: dict[DirectorySource, str] = {
    "config": "from the loaded config",
    "config_folder": "the loaded config's folder; the working directory it names does not exist",
    "launch": "the directory the overlay was started from",
    "remembered": "previously most recently used",
    "home": "your home directory",
    "selected": "selected",
}


class WorkingDirPage(QWidget):
    """"Is this your working directory?" + Change/Continue, and Load config.

    Offers, until Continue is clicked, a loaded config's working directory, else
    `launch_directory` (the directory a shell started the overlay from); after that the
    remembered most recently used directory, then the home directory. This directory seeds
    where every later file picker in the wizard starts browsing.

    Load config emits `load_config_requested` with the chosen file; the window loads it and
    calls `show_loaded_config`.
    """

    continue_requested = Signal()
    load_config_requested = Signal(Path)

    def __init__(self, launch_directory: Path | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._launch_directory = launch_directory
        self._config_directory: Path | None = None
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

        self._config_label = QLabel()
        self._config_label.setStyleSheet("color: #555;")
        self._config_label.setWordWrap(True)
        self._config_label.setVisible(False)
        layout.addWidget(self._config_label)

        layout.addStretch(1)

        buttons = QHBoxLayout()
        load_button = QPushButton("Load config")
        load_button.setToolTip("Fills in every step from a config saved on the Summary page or by Run.")
        load_button.clicked.connect(self._on_load_config)
        buttons.addWidget(load_button)
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
        if self._config_directory is not None:
            self._directory = self._config_directory
        elif self._launch_directory is not None:
            self._directory, self._source = self._launch_directory, "launch"
        elif remembered is not None:
            self._directory, self._source = remembered, "remembered"
        else:
            self._directory, self._source = Path.home(), "home"
        self._update_labels()

    def show_loaded_config(self, config_path: Path, working_directory: Path, next_step: str) -> None:
        """Offers the loaded config's `working_directory`, or the config's own folder when that
        directory does not exist, and says Continue goes on to `next_step`."""
        if working_directory.is_dir():
            self._config_directory, self._source = working_directory, "config"
        else:
            self._config_directory, self._source = config_path.parent, "config_folder"
        self._config_label.setText(
            f"Loaded {config_path}. Every step is filled in from it; Continue goes on to {next_step}."
        )
        self._config_label.setVisible(True)
        self.refresh()

    def _update_labels(self) -> None:
        self._question_label.setText(f"Is this your working directory? ({_SOURCE_NOTES[self._source]})")
        self._path_label.setText(str(self._directory))

    def _on_change(self) -> None:
        chosen = QFileDialog.getExistingDirectory(self, "Select working directory", str(self._directory))
        if chosen:
            self._directory, self._source = Path(chosen), "selected"
            self._config_directory = None
            self._update_labels()

    def _on_load_config(self) -> None:
        path = ask_config_load_path(self, self._directory)
        if path is not None:
            self.load_config_requested.emit(path)

    def _on_continue(self) -> None:
        settings.set_last_working_directory(self._directory)
        self._launch_directory = None
        self._config_directory = None
        self._config_label.setVisible(False)
        self.continue_requested.emit()

    def working_directory(self) -> Path:
        return self._directory
