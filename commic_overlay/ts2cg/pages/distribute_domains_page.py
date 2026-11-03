"""DistributeDomainsPage: DOP's curvature-driven assignment of points to domains.

DOP replaces a whole leaflet's `domain_ids`, so it runs before Place Domains. Continuing
with no rows skips it. Continuing with rows that don't sum to 1.0 normalizes them after a
confirmation, and `state.domain_count` is raised to cover every domain id referenced here.
Deleted rows go on an undo stack, restored one at a time at their former position.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from ...theme import mark_primary
from ...widgets.float_spinbox import FloatSpinBox
from ...widgets.scroll_spinbox import IntSpinBox
from ..state import DopSpec, WizardState

_PERCENTAGE_SUM_TOLERANCE = 1e-2  # DOP's parser accepts `np.isclose(total, 1.0, atol=0.01)`
_COLUMNS = ["Domain", "Percentage", "Curvature (1/nm)", ""]
_DESCRIPTION = (
    "Optional - TS2CG's DOP assigns every point of the chosen leaflets to a domain. Each row "
    "claims its percentage of the points for its domain, favoring points whose curvature "
    "(twice the local mean curvature) is close to the row's curvature; the k-factor sets how "
    "strongly. Several rows can share a domain. This decides only where the domains are; "
    "Sort Lipids decides which lipids each domain holds. DOP overwrites the domain of every "
    "point on the chosen leaflets, so it runs before Place Domains. A row referencing a "
    "domain beyond the number set on the Domains page raises that number. Continue without "
    "adding any rows to skip this."
)


class DistributeDomainsPage(QWidget):
    continue_requested = Signal()

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._deleted_rows: list[tuple[int, DopSpec]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Distribute domains (DOP)")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        description = QLabel(_DESCRIPTION)
        description.setWordWrap(True)
        description.setStyleSheet("color: #555;")
        layout.addWidget(description)

        row_buttons = QHBoxLayout()
        row_buttons.addStretch(1)
        self._undo_button = QPushButton("Undo delete row")
        self._undo_button.setToolTip("Restores the most recently deleted row (Ctrl+Z).")
        self._undo_button.setEnabled(False)
        self._undo_button.clicked.connect(self._on_undo_delete)
        row_buttons.addWidget(self._undo_button)
        add_button = QPushButton("Add row")
        add_button.clicked.connect(self._on_add_row)
        row_buttons.addWidget(add_button)
        layout.addLayout(row_buttons)

        undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        undo_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        undo_shortcut.activated.connect(self._on_undo_delete)

        self._table = QTableWidget(0, len(_COLUMNS))
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table, stretch=1)

        settings_row = QHBoxLayout()
        settings_row.addWidget(QLabel("Leaflet:"))
        self._leaflet_box = QComboBox()
        self._leaflet_box.addItems(["both", "inner", "outer"])
        self._leaflet_box.currentTextChanged.connect(self._on_leaflet_changed)
        settings_row.addWidget(self._leaflet_box)

        settings_row.addWidget(QLabel("k-factor:"))
        self._k_factor_box = FloatSpinBox(minimum=0.0, maximum=1000.0, value=1.0, step=0.1, decimals=2)
        self._k_factor_box.valueChanged.connect(self._on_k_factor_changed)
        settings_row.addWidget(self._k_factor_box)

        self._area_weighted_check = QCheckBox("Weight by point area")
        self._area_weighted_check.toggled.connect(self._on_area_weighted_changed)
        settings_row.addWidget(self._area_weighted_check)

        self._seed_check = QCheckBox("Fixed random seed")
        settings_row.addWidget(self._seed_check)
        self._seed_box = IntSpinBox()
        self._seed_box.setEnabled(False)
        self._seed_check.toggled.connect(self._on_seed_toggled)
        settings_row.addWidget(self._seed_box)
        settings_row.addStretch(1)
        layout.addLayout(settings_row)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._continue_button = QPushButton("Continue")
        mark_primary(self._continue_button)
        self._continue_button.clicked.connect(self._on_continue_clicked)
        buttons.addWidget(self._continue_button)
        layout.addLayout(buttons)

    def refresh(self) -> None:
        self._leaflet_box.blockSignals(True)
        self._leaflet_box.setCurrentText(self._state.dop_leaflet)
        self._leaflet_box.blockSignals(False)
        self._k_factor_box.blockSignals(True)
        self._k_factor_box.setValue(self._state.dop_k_factor)
        self._k_factor_box.blockSignals(False)
        self._area_weighted_check.blockSignals(True)
        self._area_weighted_check.setChecked(self._state.dop_area_weighted)
        self._area_weighted_check.blockSignals(False)
        self._seed_check.blockSignals(True)
        self._seed_check.setChecked(self._state.dop_seed is not None)
        self._seed_box.setEnabled(self._state.dop_seed is not None)
        self._seed_box.setValue(self._state.dop_seed or 0)
        self._seed_check.blockSignals(False)
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        rows = self._state.dop_specs
        self._table.setRowCount(len(rows))
        for row_index, spec in enumerate(rows):
            domain_box = IntSpinBox(minimum=0, maximum=1000, value=spec.domain_id)
            domain_box.valueChanged.connect(lambda value, s=spec: setattr(s, "domain_id", value))
            self._table.setCellWidget(row_index, 0, domain_box)

            percentage_box = FloatSpinBox(minimum=0.0, maximum=1.0, value=spec.percentage, step=0.05, decimals=3)
            percentage_box.valueChanged.connect(lambda value, s=spec: setattr(s, "percentage", value))
            self._table.setCellWidget(row_index, 1, percentage_box)

            curvature_box = FloatSpinBox(minimum=-10.0, maximum=10.0, value=spec.curvature, step=0.01, decimals=3)
            curvature_box.valueChanged.connect(lambda value, s=spec: setattr(s, "curvature", value))
            self._table.setCellWidget(row_index, 2, curvature_box)

            delete_button = QPushButton("Delete row")
            delete_button.clicked.connect(lambda _checked, s=spec: self._on_delete_row(s))
            self._table.setCellWidget(row_index, 3, delete_button)

        self._table.resizeColumnsToContents()
        self._undo_button.setEnabled(bool(self._deleted_rows))

    def _on_add_row(self) -> None:
        self._state.dop_specs.append(DopSpec(domain_id=0))
        self._rebuild_table()

    def _on_delete_row(self, spec: DopSpec) -> None:
        index = next(i for i, s in enumerate(self._state.dop_specs) if s is spec)
        self._deleted_rows.append((index, spec))
        del self._state.dop_specs[index]
        self._rebuild_table()

    def _on_undo_delete(self) -> None:
        if not self._deleted_rows:
            return
        index, spec = self._deleted_rows.pop()
        self._state.dop_specs.insert(min(index, len(self._state.dop_specs)), spec)
        self._rebuild_table()

    def _on_leaflet_changed(self, text: str) -> None:
        self._state.dop_leaflet = text

    def _on_k_factor_changed(self, value: float) -> None:
        self._state.dop_k_factor = value

    def _on_area_weighted_changed(self, checked: bool) -> None:
        self._state.dop_area_weighted = checked

    def _on_seed_toggled(self, checked: bool) -> None:
        self._seed_box.setEnabled(checked)
        self._state.dop_seed = self._seed_box.value() if checked else None

    def _percentage_sum(self) -> float:
        return sum(s.percentage for s in self._state.dop_specs)

    def _on_continue_clicked(self) -> None:
        self._state.dop_seed = self._seed_box.value() if self._seed_check.isChecked() else None

        if self._state.dop_specs and abs(self._percentage_sum() - 1.0) > _PERCENTAGE_SUM_TOLERANCE:
            answer = QMessageBox.warning(
                self,
                "Percentages don't sum to 1",
                "DOP requires every row's percentage, across the whole file, to sum to "
                "1.0. They will now be normalized to 1.",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Ok:
                return
            self._normalize_percentages()
            self._rebuild_table()

        if self._state.dop_specs:
            highest_domain_id = max(s.domain_id for s in self._state.dop_specs)
            self._state.domain_count = max(self._state.domain_count, highest_domain_id + 1)

        self.continue_requested.emit()

    def _normalize_percentages(self) -> None:
        total = self._percentage_sum()
        if total > 0:
            for spec in self._state.dop_specs:
                spec.percentage = spec.percentage / total
