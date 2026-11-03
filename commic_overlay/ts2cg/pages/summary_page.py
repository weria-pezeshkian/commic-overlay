"""SummaryPage: wall-beads toggle, Advanced, and Continue -> Run."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...theme import mark_primary
from ..state import WizardState
from ..ts2cg_bridge.preview_membrane import prune_domain_ops
from .advanced_window import AdvancedWindow


class SummaryPage(QWidget):
    advanced_requested = Signal()
    run_requested = Signal()

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Summary")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        self._summary_label = QLabel("")
        self._summary_label.setWordWrap(True)
        self._summary_label.setStyleSheet("color: #555;")
        layout.addWidget(self._summary_label)

        self._wall_check = QCheckBox("Add wall beads")
        self._wall_check.setToolTip("Creates a wall around the membrane (TS2CG PCG's own -Wall flag).")
        self._wall_check.toggled.connect(self._on_wall_toggled)
        layout.addWidget(self._wall_check)

        layout.addStretch(1)

        buttons_row = QHBoxLayout()
        advanced_button = QPushButton("Advanced")
        advanced_button.clicked.connect(self._on_advanced_clicked)
        buttons_row.addWidget(advanced_button)
        buttons_row.addStretch(1)
        self._run_button = QPushButton("Continue")
        mark_primary(self._run_button)
        self._run_button.clicked.connect(self.run_requested)
        buttons_row.addWidget(self._run_button)
        layout.addLayout(buttons_row)

    def refresh(self) -> None:
        prune_domain_ops(self._state)
        self._wall_check.blockSignals(True)
        self._wall_check.setChecked(self._state.add_wall_beads)
        self._wall_check.blockSignals(False)
        self._summary_label.setText(self._build_summary_text())

    def _build_summary_text(self) -> str:
        lines = [f"Path: {self._state.path_choice or '(not set)'}"]
        if self._state.path_choice == "analytical_shape":
            lines.append(f"Shape: {self._state.shape_type or '(not set)'}")
        else:
            lines.append(f"Mesh file: {self._state.mesh_file_path or '(not set)'}")
        lines.append(f"Lipids: {len(self._state.selected_lipids)} selected")
        lines.append(f"Domains: {self._state.domain_count}")
        lines.append(f"Proteins: {len(self._state.proteins)} added")
        lines.append(f"Domain operations: {len(self._state.domain_ops)}")
        return "\n".join(lines)

    def _on_wall_toggled(self, checked: bool) -> None:
        self._state.add_wall_beads = checked

    def _on_advanced_clicked(self) -> None:
        dialog = AdvancedWindow(self._state, self)
        dialog.exec()
