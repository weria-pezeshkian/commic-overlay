"""MeshFilePage: pick a .tsi/.vtk/.vtu/.blend file - TS2CG's own mesh-based path."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...theme import mark_primary
from ..availability import blender_converter_available, vtk_converter_available
from ..state import WizardState


class MeshFilePage(QWidget):
    """Load + Continue, same pattern as CALM's own structure_page.py - `.tsi` is always
    accepted (TS2CG reads it natively, no converter needed); `.vtk`/`.vtu` and `.blend` each
    need their own optional converter dependency (`availability.py`), checked independently
    here rather than lumped into one "converter available" flag - either is simply left out
    of the file dialog's own filter, with an explanatory note, when not actually usable.
    """

    continue_requested = Signal()

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Select a mesh file")
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

        self._converter_note = QLabel("")
        self._converter_note.setStyleSheet("color: #999; font-size: 12px;")
        self._converter_note.setWordWrap(True)
        layout.addWidget(self._converter_note)

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
        self._show_path(self._state.mesh_file_path or None)
        self._update_converter_note()

    def _update_converter_note(self) -> None:
        missing = []
        if not vtk_converter_available():
            missing.append(".vtk/.vtu (needs the optional 'vtk' package)")
        if not blender_converter_available():
            missing.append(".blend (needs a 'blender' executable on PATH)")
        if missing:
            self._converter_note.setText(
                "Not available in this environment: " + "; ".join(missing) + ". .tsi is always supported."
            )
        else:
            self._converter_note.setText("")

    def _on_load(self) -> None:
        start_dir = str(self._state.working_directory)
        extensions = ["*.tsi"]
        if vtk_converter_available():
            extensions += ["*.vtk", "*.vtu"]
        if blender_converter_available():
            extensions += ["*.blend"]
        filter_str = f"Mesh files ({' '.join(extensions)});;All files (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Select mesh file", start_dir, filter_str)
        if not path:
            return
        suffix = Path(path).suffix.lower()
        if suffix in (".vtk", ".vtu") and not vtk_converter_available():
            self._path_label.setText("The 'vtk' package isn't available - cannot use a .vtk/.vtu file.")
            return
        if suffix == ".blend" and not blender_converter_available():
            self._path_label.setText("No 'blender' executable on PATH - cannot use a .blend file.")
            return
        self._state.mesh_file_path = path
        self._show_path(path)

    def _show_path(self, path: str | None) -> None:
        self._path_label.setText(path or "No file selected.")
        self._continue_button.setEnabled(bool(path))
