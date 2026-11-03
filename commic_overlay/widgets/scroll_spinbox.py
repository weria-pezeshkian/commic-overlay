"""IntSpinBox, the integer control for the wizards' count, id and seed fields, and
StrideSpinBox, its minimum-1 form used for the Trajectory page's stride."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFocusEvent, QWheelEvent
from PySide6.QtWidgets import QAbstractScrollArea, QSpinBox, QWidget


def inside_scroll_area(widget: QWidget) -> bool:
    """Whether `widget` sits inside a scroll area, a table included."""
    parent = widget.parentWidget()
    while parent is not None:
        if isinstance(parent, QAbstractScrollArea):
            return True
        parent = parent.parentWidget()
    return False


def wheel_steps_spin_box(widget: QWidget) -> bool:
    """Whether a wheel event over spin box `widget` steps its value: always outside a scroll
    area, and inside one only while the spin box has focus, so the wheel scrolls the page."""
    return widget.hasFocus() or not inside_scroll_area(widget)


class IntSpinBox(QSpinBox):
    """Integer control between `minimum` and `maximum`.

    Gaining focus selects the whole text, so typing replaces the value instead of being
    inserted next to the old digits ("1" -> "51").

    The mouse wheel steps the value on hover, with no prior click needed, except inside a
    scroll area or table: there it steps only while focused and otherwise scrolls the page
    (`wheel_steps_spin_box`).
    """

    def __init__(
        self, minimum: int = 0, maximum: int = 2_147_483_647, value: int = 0, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setMinimum(minimum)
        self.setMaximum(maximum)
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


class StrideSpinBox(IntSpinBox):
    """Integer stride control, minimum 1, defaulting to 1. The decrement arrow disables
    itself at 1, `QAbstractSpinBox`'s standard behavior at its minimum."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(minimum=1, maximum=1_000_000, value=1, parent=parent)
