"""AngleControl: an angle from 0° to 360°, as a slider in whole degrees beside a spin box
holding the exact value."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QSlider, QWidget

from .float_spinbox import FloatSpinBox

_FULL_TURN = 360
_SLIDER_MINIMUM_WIDTH = 160


class AngleControl(QWidget):
    """`valueChanged` carries the spin box's value, which the slider follows and sets."""

    valueChanged = Signal(float)  # noqa: N815 (Qt signal naming)

    def __init__(self, value: float = 0.0, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, _FULL_TURN)
        self._slider.setMinimumWidth(_SLIDER_MINIMUM_WIDTH)
        layout.addWidget(self._slider, stretch=1)

        self._box = FloatSpinBox(minimum=0.0, maximum=float(_FULL_TURN), value=value, step=1.0, decimals=1)
        self._box.setSuffix("°")
        self._box.setWrapping(True)
        layout.addWidget(self._box)

        self._slider.setValue(round(value))
        self._slider.valueChanged.connect(self._on_slider_moved)
        self._box.valueChanged.connect(self._on_box_changed)

    def value(self) -> float:
        return self._box.value()

    def setValue(self, value: float) -> None:  # noqa: N802 (Qt naming, like the spin box it wraps)
        self._box.setValue(value)

    def _on_slider_moved(self, degrees: int) -> None:
        if round(self._box.value()) != degrees:
            self._box.setValue(float(degrees))

    def _on_box_changed(self, value: float) -> None:
        self._slider.blockSignals(True)
        self._slider.setValue(round(value))
        self._slider.blockSignals(False)
        self.valueChanged.emit(value)
