"""PathChoicePage: analytical shape vs an existing mesh file - TS2CG's own two starting points."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..state import WizardState


class PathChoicePage(QWidget):
    """TS2CG builds a membrane from one of two starting points: an existing triangulated
    surface (or a Blender/VTK mesh converted to one) or a purely analytical shape with no
    input file at all. Picking one here decides which page comes next
    (`analytical_shape_page.py` or `mesh_file_page.py`) and is recorded on `state.path_choice`
    so later pages, and the Run pipeline, know which branch's own parameters to read.
    """

    path_chosen = Signal(str)  # "analytical_shape" | "mesh_file"

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Choose your path")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        subtitle = QLabel("How should the membrane's own shape be built?")
        subtitle.setStyleSheet("color: #555;")
        layout.addWidget(subtitle)

        layout.addStretch(1)

        choices_row = QHBoxLayout()
        choices_row.setSpacing(24)
        choices_row.addWidget(
            self._build_choice(
                "Analytical shape",
                "Flat, sphere, cylinder, or a 1D periodic Fourier shape - built purely from "
                "parameters, no input file needed.",
                "analytical_shape",
            )
        )
        choices_row.addWidget(
            self._build_choice(
                "From a file",
                "A .tsi, .blend, or .vtk mesh - typically the output of a dynamically "
                "triangulated surface simulation, or electron-microscopy tomography data.",
                "mesh_file",
            )
        )
        layout.addLayout(choices_row)

        layout.addStretch(1)

    def refresh(self) -> None:
        pass

    def _build_choice(self, title: str, description: str, key: str) -> QWidget:
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setSpacing(8)

        button = QPushButton(title)
        button.setMinimumHeight(56)
        button.setStyleSheet("font-size: 16px; font-weight: 600;")
        button.clicked.connect(lambda: self._on_choice_clicked(key))
        container_layout.addWidget(button)

        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setStyleSheet("color: #777; font-size: 12px;")
        description_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        container_layout.addWidget(description_label, stretch=1)

        return container

    def _on_choice_clicked(self, key: str) -> None:
        self._state.path_choice = key
        self.path_chosen.emit(key)
