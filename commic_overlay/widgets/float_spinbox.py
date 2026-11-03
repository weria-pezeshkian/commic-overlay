"""FloatSpinBox: the float control for TS2CG parameters (box dimensions, thickness, radius,
density, ...), with the same mouse-wheel and focus behavior as `scroll_spinbox.IntSpinBox`."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFocusEvent, QWheelEvent
from PySide6.QtWidgets import QDoubleSpinBox, QWidget

from .scroll_spinbox import wheel_steps_spin_box


class FloatSpinBox(QDoubleSpinBox):
    """A bounded float control: `minimum`/`maximum` are enforced by the widget itself, so a
    value this page's Continue hands to a real TS2CG call stays inside them.

    Gaining focus selects the whole text, so typing replaces the value. A spin box showing
    all its decimals rejects any digit typed at the cursor (e.g. "0.000" -> "0.0005"), so
    typing into it looked like it did nothing. The mouse wheel steps the value on hover,
    with no prior click needed, except inside a scroll area or table: there it steps only
    while focused and otherwise scrolls the page (`scroll_spinbox.wheel_steps_spin_box`).
    """

    def __init__(
        self,
        minimum: float = 0.0,
        maximum: float = 1_000_000.0,
        value: float = 0.0,
        step: float = 0.1,
        decimals: int = 2,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimum(minimum)
        self.setMaximum(maximum)
        self.setDecimals(decimals)
        self.setSingleStep(step)
        self.setValue(value)

    def focusInEvent(self, event: QFocusEvent) -> None:  # noqa: N802 (Qt override, not our naming convention)
        super().focusInEvent(event)
        # After the click that gave focus has placed the cursor.
        QTimer.singleShot(0, self, self.selectAll)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 (Qt override, not our naming convention)
        if not wheel_steps_spin_box(self):
            event.ignore()
            return
        delta = event.angleDelta().y()
        if delta != 0:
            self.stepBy(1 if delta > 0 else -1)
        event.accept()
