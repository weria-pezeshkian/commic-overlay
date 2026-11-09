"""AddProteinPage: the wizard step listing every added protein, with "Add protein" and each
row's "Edit" opening the live-preview popup (`add_protein_dialog.py`). Optional - zero
proteins is a valid run."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...theme import mark_primary
from ..state import ProteinSpec, WizardState
from .add_protein_dialog import AddProteinDialog

_COLUMNS = ["Type", "Name", "Count", "Z0 (nm)", "Rotation x, y", "", ""]


class AddProteinPage(QWidget):
    continue_requested = Signal()

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Add proteins")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        description = QLabel(
            "Optional - embed one or more proteins in the membrane. Continue without adding any to skip this."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #555;")
        layout.addWidget(description)

        add_row = QHBoxLayout()
        add_row.addStretch(1)
        add_button = QPushButton("Add protein")
        add_button.clicked.connect(self._on_add_clicked)
        add_row.addWidget(add_button)
        layout.addLayout(add_row)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table, stretch=1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._continue_button = QPushButton("Continue")
        mark_primary(self._continue_button)
        self._continue_button.clicked.connect(self.continue_requested)
        buttons.addWidget(self._continue_button)
        layout.addLayout(buttons)

    def refresh(self) -> None:
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        self._table.setRowCount(len(self._state.proteins))
        for row, protein in enumerate(self._state.proteins):
            self._table.setItem(row, 0, QTableWidgetItem(str(protein.type_id)))
            self._table.setItem(row, 1, QTableWidgetItem(protein.name))
            self._table.setItem(row, 2, QTableWidgetItem(str(protein.num_proteins)))
            self._table.setItem(row, 3, QTableWidgetItem(f"{protein.z0:.2f}"))
            rotation_item = QTableWidgetItem(f"{protein.rotation_x:.1f}°, {protein.rotation_y:.1f}°")
            if protein.align_principal_axis:
                rotation_item.setText(f"aligned + {rotation_item.text()}")
                rotation_item.setToolTip("Aligned z to the principal axis, then rotated by these angles.")
            self._table.setItem(row, 4, rotation_item)
            edit_button = QPushButton("Edit")
            edit_button.clicked.connect(lambda _checked, p=protein: self._on_edit(p))
            self._table.setCellWidget(row, 5, edit_button)
            remove_button = QPushButton("Delete row")
            remove_button.clicked.connect(lambda _checked, p=protein: self._on_remove(p))
            self._table.setCellWidget(row, 6, remove_button)
        self._table.resizeColumnsToContents()

    def _on_edit(self, protein: ProteinSpec) -> None:
        """Reopens the dialog on `protein`; Save replaces it in place, under the same type id."""
        dialog = AddProteinDialog(self._state, protein.type_id, existing=protein, parent=self)
        if dialog.exec() == AddProteinDialog.DialogCode.Accepted:
            edited = dialog.result_protein()
            if edited is not None:
                index = next(i for i, p in enumerate(self._state.proteins) if p is protein)
                self._state.proteins[index] = edited
                self._rebuild_table()

    def _on_remove(self, protein: ProteinSpec) -> None:
        self._state.proteins = [p for p in self._state.proteins if p is not protein]
        self._rebuild_table()

    def _next_type_id(self) -> int:
        used = {p.type_id for p in self._state.proteins}
        candidate = 1
        while candidate in used:
            candidate += 1
        return candidate

    def _on_add_clicked(self) -> None:
        dialog = AddProteinDialog(self._state, self._next_type_id(), parent=self)
        if dialog.exec() == AddProteinDialog.DialogCode.Accepted:
            protein = dialog.result_protein()
            if protein is not None:
                self._state.proteins.append(protein)
                self._rebuild_table()
