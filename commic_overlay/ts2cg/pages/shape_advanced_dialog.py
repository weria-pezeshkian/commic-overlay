"""ShapeAdvancedDialog: the analytical shape's advanced `[Shape Data]` fields, and the grid-row
builder the Analytical Shape page shares with it."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from PySide6.QtWidgets import QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...theme import mark_primary
from ...widgets.float_spinbox import FloatSpinBox
from ..ts2cg_bridge.shape_fields import ShapeField

_SUB_LABEL_STYLE = "color: #777; font-size: 11px;"


def add_field_rows(
    grid: QGridLayout, row: int, field: ShapeField, values: list[float], on_change: Callable[[str, int, float], None]
) -> int:
    """Adds `field` to `grid` at `row`: its label, then one sub-label over one spin box per
    value. A changed box calls `on_change(field.name, index, value)`. Returns the next free row."""
    label = QLabel(field.label)
    label.setToolTip(field.help)
    grid.addWidget(label, row + 1, 0)
    for index, sub_label in enumerate(field.sub_labels):
        sub = QLabel(sub_label)
        sub.setStyleSheet(_SUB_LABEL_STYLE)
        grid.addWidget(sub, row, index + 1)
        box = FloatSpinBox(minimum=field.minimum, maximum=field.maximum, value=values[index], step=0.1, decimals=3)
        box.setToolTip(field.help)
        box.valueChanged.connect(partial(on_change, field.name, index))
        grid.addWidget(box, row + 1, index + 1)
    return row + 2


class ShapeAdvancedDialog(QDialog):
    """Edits a copy of the advanced fields' values; `values()` returns them after Apply."""

    def __init__(
        self, fields: tuple[ShapeField, ...], values: dict[str, list[float]], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Advanced shape settings")
        self._values = {field.name: list(values[field.name]) for field in fields}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        row = 0
        for field in fields:
            row = add_field_rows(grid, row, field, self._values[field.name], self._on_value_changed)
            help_label = QLabel(field.help)
            help_label.setWordWrap(True)
            help_label.setStyleSheet(_SUB_LABEL_STYLE)
            grid.addWidget(help_label, row, 1, 1, 4)
            row += 1
            grid.setRowMinimumHeight(row, 8)
            row += 1
        layout.addLayout(grid)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons_row.addWidget(cancel_button)
        apply_button = QPushButton("Apply")
        mark_primary(apply_button)
        apply_button.clicked.connect(self.accept)
        buttons_row.addWidget(apply_button)
        layout.addLayout(buttons_row)

    def _on_value_changed(self, name: str, index: int, value: float) -> None:
        self._values[name][index] = value

    def values(self) -> dict[str, list[float]]:
        return self._values
