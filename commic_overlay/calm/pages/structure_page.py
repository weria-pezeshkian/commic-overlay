"""StructurePage: pick the structure file."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...theme import mark_primary
from ..state import WizardState


class StructurePage(QWidget):
    continue_requested = Signal()

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Please select your structure")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        path_row = QHBoxLayout()
        self._path_label = QLabel("No file selected.")
        self._path_label.setStyleSheet("color: #555;")
        self._path_label.setWordWrap(True)
        path_row.addWidget(self._path_label, stretch=1)
        load_button = QPushButton("Load")
        load_button.clicked.connect(self._on_load)
        path_row.addWidget(load_button)
        layout.addLayout(path_row)

        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._continue_button = QPushButton("Continue")
        mark_primary(self._continue_button)
        self._continue_button.setEnabled(False)
        self._continue_button.clicked.connect(self.continue_requested)
        buttons.addWidget(self._continue_button)
        layout.addLayout(buttons)

    def refresh(self) -> None:
        """Re-displays whatever self._state.structure_path currently is - call each time
        this page is shown, so an edit made elsewhere (the Advanced window) shows up here
        too, not just a path picked through this page's own Load button."""
        self._show_path(self._state.structure_path)

    def _on_load(self) -> None:
        start_dir = str(self._state.working_directory)
        path, _ = QFileDialog.getOpenFileName(
            self, "Select structure file", start_dir, "Structure files (*.gro *.tpr *.pdb);;All files (*)"
        )
        if path:
            self._state.structure_path = path
            self._show_path(path)

    def _show_path(self, path: str | None) -> None:
        self._path_label.setText(path or "No file selected.")
        self._continue_button.setEnabled(bool(path))
