"""StrideSpinBox: the small up/down stride control used on the Trajectory page."""

from __future__ import annotations

from PySide6.QtWidgets import QSpinBox, QWidget


class StrideSpinBox(QSpinBox):
    """Integer stride control, minimum 1, defaulting to 1.

    Up/down arrows only (Qt's own default spin-box buttons) - the
    decrement arrow disables itself automatically once the value reaches
    1, since that's already `QAbstractSpinBox`'s standard behavior at its
    configured minimum; nothing extra is needed for that part.

    Responds to the mouse wheel on hover, with no prior click needed to
    give it keyboard focus first. `QAbstractSpinBox`'s own default
    `wheelEvent` only steps the value while the widget already has focus,
    specifically so a spin box embedded in a scrollable container (a
    table cell, a form inside a `QScrollArea`) doesn't eat the
    container's own scroll gesture - that default is overridden here
    since this control is never embedded in anything scrollable.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimum(1)
        self.setMaximum(1_000_000)
        self.setValue(1)

    def wheelEvent(self, event) -> None:  # noqa: N802 (Qt override, not our naming convention)
        delta = event.angleDelta().y()
        if delta != 0:
            self.stepBy(1 if delta > 0 else -1)
        event.accept()
