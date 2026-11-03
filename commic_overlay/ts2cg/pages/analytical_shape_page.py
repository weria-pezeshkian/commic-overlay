"""AnalyticalShapePage: pick a ShapeType, fill in its `[Shape Data]` parameters, see a live 3D
preview of the shape inside its box, drawn to scale.

Each shape's basic fields (`ts2cg_bridge/shape_fields.py`) are always shown, above the preview,
which takes the remaining height; the advanced fields open in `ShapeAdvancedDialog`. Each shape
keeps its own values while the page lives, starting from its own defaults.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from PySide6.QtCore import Signal  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QButtonGroup,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...theme import mark_primary  # noqa: E402
from ...widgets.float_spinbox import FloatSpinBox  # noqa: E402
from ..state import WizardState  # noqa: E402
from ..ts2cg_bridge.shape_fields import (  # noqa: E402
    SHAPE_FIELDS,
    advanced_fields,
    basic_fields,
    initial_values,
    shape_params,
)
from ..ts2cg_bridge.shape_preview import box_edges, shape_preview  # noqa: E402
from .shape_advanced_dialog import ShapeAdvancedDialog, add_field_rows  # noqa: E402

_SHAPE_LABELS = {
    "Flat": "Flat",
    "Sphere": "Sphere",
    "Cylinder": "Cylinder",
    "1D_PBC_Fourier": "1D Fourier shape",
}
_SHAPE_ORDER = ["Flat", "Sphere", "Cylinder", "1D_PBC_Fourier"]
_MODE_HEADERS = ("Amplitude A (nm)", "n", "Phase (°)")
_MODE_HELP = "z(x) = Z/2 + A·cos(2π·n·x/X + phase), summed over the modes."
_PREVIEW_MINIMUM_HEIGHT = 160
_PREVIEW_ZOOM = 0.85  # shrinks the 3D box inside the canvas so the tick labels fit
_STRETCH_COLUMN = 5  # right of the widest row: a mode's three boxes and its Delete row button

ModeRow = tuple[list[QWidget], FloatSpinBox, FloatSpinBox, FloatSpinBox]


class AnalyticalShapePage(QWidget):
    continue_requested = Signal()

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._values: dict[str, list[float]] = {}
        self._mode_rows: list[ModeRow] = []
        self._form_widget: QWidget | None = None
        self._params_by_shape: dict[str, dict[str, object]] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Analytical shape")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        body = QHBoxLayout()
        body.setSpacing(24)

        shapes_column = QVBoxLayout()
        shapes_column.setSpacing(8)
        self._shape_group = QButtonGroup(self)
        self._shape_group.setExclusive(True)
        self._shape_buttons: dict[str, QPushButton] = {}
        for shape in _SHAPE_ORDER:
            button = QPushButton(_SHAPE_LABELS[shape])
            button.setCheckable(True)
            button.clicked.connect(lambda _checked, s=shape: self._on_shape_selected(s))
            self._shape_group.addButton(button)
            self._shape_buttons[shape] = button
            shapes_column.addWidget(button)
        shapes_column.addStretch(1)
        shapes_widget = QWidget()
        shapes_widget.setLayout(shapes_column)
        shapes_widget.setFixedWidth(160)
        body.addWidget(shapes_widget)

        right_column = QVBoxLayout()
        right_column.setSpacing(12)

        self._form_holder = QVBoxLayout()
        self._form_holder.setContentsMargins(0, 0, 0, 0)
        right_column.addLayout(self._form_holder)

        self._figure = Figure(figsize=(5, 4))
        self._figure.subplots_adjust(left=0.0, right=1.0, bottom=0.0, top=1.0)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setMinimumHeight(_PREVIEW_MINIMUM_HEIGHT)
        self._axes = self._figure.add_subplot(projection="3d")
        right_column.addWidget(self._canvas, stretch=1)

        body.addLayout(right_column, stretch=1)
        layout.addLayout(body, stretch=1)

        buttons_row = QHBoxLayout()
        self._advanced_button = QPushButton("Advanced shape settings")
        self._advanced_button.clicked.connect(self._on_advanced_clicked)
        buttons_row.addWidget(self._advanced_button)
        buttons_row.addStretch(1)
        self._continue_button = QPushButton("Continue")
        mark_primary(self._continue_button)
        self._continue_button.setEnabled(False)
        self._continue_button.clicked.connect(self.continue_requested)
        buttons_row.addWidget(self._continue_button)
        layout.addLayout(buttons_row)

    def refresh(self) -> None:
        """Re-selects whatever self._state.shape_type currently is - call each time this
        page is shown, mirroring every other page's own refresh() contract."""
        shape = self._state.shape_type or "Flat"
        if shape not in SHAPE_FIELDS:
            shape = "Flat"
        self._shape_buttons[shape].setChecked(True)
        self._build_form_for(shape)

    def _on_shape_selected(self, shape: str) -> None:
        self._build_form_for(shape)

    def _build_form_for(self, shape: str) -> None:
        if self._state.shape_type == shape and self._state.shape_params:
            existing = dict(self._state.shape_params)
        else:
            existing = self._params_by_shape.get(shape, {})
        self._state.shape_type = shape
        self._values = initial_values(shape, existing)
        self._mode_rows = []

        if self._form_widget is not None:
            self._form_holder.removeWidget(self._form_widget)
            self._form_widget.hide()
            self._form_widget.deleteLater()
        self._form_widget = QWidget()
        grid = QGridLayout(self._form_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setVerticalSpacing(4)
        grid.setHorizontalSpacing(8)

        row = 0
        for field in basic_fields(shape):
            row = add_field_rows(grid, row, field, self._values[field.name], self._on_value_changed)

        if shape == "1D_PBC_Fourier":
            for index, header in enumerate(_MODE_HEADERS):
                header_label = QLabel(header)
                header_label.setStyleSheet("color: #777; font-size: 11px;")
                grid.addWidget(header_label, row, index + 1)
            modes_label = QLabel("Modes")
            modes_label.setToolTip(_MODE_HELP)
            grid.addWidget(modes_label, row + 1, 0)
            add_mode_button = QPushButton("Add mode")
            add_mode_button.setToolTip(_MODE_HELP)
            add_mode_button.clicked.connect(self._on_add_mode)
            grid.addWidget(add_mode_button, row + 1, 1)
            self._modes_grid = grid
            self._modes_next_row = row + 2
            for mode in existing.get("Modes", []):
                self._add_mode_row(float(mode[0]), float(mode[1]), float(mode[2]))

        grid.setColumnStretch(_STRETCH_COLUMN, 1)
        self._form_holder.addWidget(self._form_widget)
        self._advanced_button.setEnabled(bool(advanced_fields(shape)))
        self._update_params()
        self._continue_button.setEnabled(True)

    def _on_value_changed(self, name: str, index: int, value: float) -> None:
        self._values[name][index] = value
        self._update_params()

    def _on_advanced_clicked(self) -> None:
        dialog = ShapeAdvancedDialog(advanced_fields(self._state.shape_type), self._values, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._values.update(dialog.values())
            self._update_params()

    def _on_add_mode(self) -> None:
        self._add_mode_row(1.0, 1.0, 0.0)
        self._update_params()

    def _add_mode_row(self, amplitude: float, n: float, phi: float) -> None:
        a_box = FloatSpinBox(minimum=-100.0, maximum=100.0, value=amplitude, step=0.1, decimals=3)
        n_box = FloatSpinBox(minimum=0.0, maximum=100.0, value=n, step=1.0, decimals=0)
        phi_box = FloatSpinBox(minimum=-360.0, maximum=360.0, value=phi, step=5.0, decimals=1)
        remove_button = QPushButton("Delete row")
        widgets: list[QWidget] = [a_box, n_box, phi_box, remove_button]
        for column, widget in enumerate(widgets, start=1):
            self._modes_grid.addWidget(widget, self._modes_next_row, column)
        for box in (a_box, n_box, phi_box):
            box.valueChanged.connect(self._update_params)
        remove_button.clicked.connect(lambda: self._on_remove_mode(widgets))
        self._modes_next_row += 1
        self._mode_rows.append((widgets, a_box, n_box, phi_box))

    def _on_remove_mode(self, widgets: list[QWidget]) -> None:
        self._mode_rows = [r for r in self._mode_rows if r[0] is not widgets]
        for widget in widgets:
            self._modes_grid.removeWidget(widget)
            widget.hide()
            widget.deleteLater()
        self._update_params()

    def _update_params(self, *_args: object) -> None:
        params = shape_params(self._values)
        if self._state.shape_type == "1D_PBC_Fourier":
            params["Modes"] = [
                (a_box.value(), n_box.value(), phi_box.value()) for _w, a_box, n_box, phi_box in self._mode_rows
            ]
        self._state.shape_params = params
        self._params_by_shape[self._state.shape_type] = params
        self._redraw_preview()

    def _redraw_preview(self) -> None:
        shape = self._state.shape_type
        if not shape:
            return
        try:
            upper, lower = shape_preview(shape, self._state.shape_params)
        except (ValueError, ZeroDivisionError):
            return
        box = self._values["Box"]
        self._axes.clear()
        self._axes.scatter(upper[:, 0], upper[:, 1], upper[:, 2], s=2, c="#2a6fdb", label="Upper")
        self._axes.scatter(lower[:, 0], lower[:, 1], lower[:, 2], s=2, c="#db7f2a", label="Lower")
        for start, end in box_edges(box):
            self._axes.plot(*zip(start, end, strict=True), color="#9a9a9a", linewidth=0.8)
        self._axes.set_xlim(0.0, box[0])
        self._axes.set_ylim(0.0, box[1])
        self._axes.set_zlim(0.0, box[2])
        self._axes.set_box_aspect(box, zoom=_PREVIEW_ZOOM)
        self._axes.tick_params(labelsize=7, pad=0)
        self._axes.set_xlabel("x (nm)", fontsize=8, labelpad=0)
        self._axes.set_ylabel("y (nm)", fontsize=8, labelpad=0)
        self._axes.set_zlabel("z (nm)", fontsize=8, labelpad=0)
        self._canvas.draw_idle()
