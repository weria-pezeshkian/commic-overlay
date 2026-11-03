"""DomainOpDialog: the settings window of one Place Domains operation.

The 3D view shows the outer leaflet of the preview membrane, colored by the domains and
pores already recorded before this operation. Picked ids index that leaflet, and
`dai_bridge.py` applies them at the same location on the inner leaflet.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...theme import mark_primary
from ...widgets.float_spinbox import FloatSpinBox
from ...widgets.point_picker_3d import PointPicker3D
from ..state import DomainOp, WizardState

EXCLUSION_LABEL = -3
_EXCLUSION_COLOR = "#222222"
_DEFAULT_RADIUS = 2.0
_PALETTE = ["#b0b0b0", "#2a6fdb", "#d9534f", "#5cb85c", "#f0ad4e", "#9b59b6", "#1abc9c", "#e67e22"]
_ICON_SIZE = 12

_TITLES = {
    "dai_point": "Add domain around point",
    "dai_inclusion": "Add domain around inclusion",
    "exclusion": "Add exclusion",
}
_HELP_TEXT = {
    "dai_point": (
        "Adds ONE circular domain around the selected point(s). Use Add domain around point "
        "again to add another circular domain on top. Click a point to select it and "
        "shift-click to select several."
    ),
    "dai_inclusion": (
        "Adds ONE circular domain around every placed inclusion of the chosen protein type. "
        "Use Add domain around inclusion again to add another circular domain on top."
    ),
    "exclusion": (
        "Adds one pore at the selected point. It removes the lipids around that point on "
        "both leaflets and keeps the domains unchanged."
    ),
}
_VIEW_HELP = "Drag to rotate, scroll to zoom. The view shows the outer leaflet."
_UNSEEDED_PROTEIN_NOTE = (
    "This protein has no fixed seed, so the Run places it at different random positions "
    "than the ones shown here."
)


def domain_color(state: WizardState, domain_id: int) -> str:
    return state.domain_colors.setdefault(domain_id, _PALETTE[domain_id % len(_PALETTE)])


def color_icon(color: str) -> QIcon:
    pixmap = QPixmap(_ICON_SIZE, _ICON_SIZE)
    pixmap.fill(QColor(color))
    return QIcon(pixmap)


def _label_colors(state: WizardState, labels: np.ndarray) -> dict[int, str]:
    colors = {label: domain_color(state, label) for label in np.unique(labels).tolist() if label >= 0}
    colors[EXCLUSION_LABEL] = _EXCLUSION_COLOR
    return colors


class DomainOpDialog(QDialog):
    REMOVE_RESULT = 2

    def __init__(
        self,
        state: WizardState,
        kind: str,
        membrane: Any,
        labels: np.ndarray,
        existing_op: DomainOp | None = None,
        later_op_count: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._kind = kind
        self._membrane = membrane
        self._result: DomainOp | None = None

        self.setWindowTitle(_TITLES[kind])
        self.resize(680, 720)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        help_label = QLabel(f"{_HELP_TEXT[kind]} {_VIEW_HELP}")
        help_label.setWordWrap(True)
        help_label.setStyleSheet("color: #555;")
        layout.addWidget(help_label)

        if later_op_count > 0:
            truncation_label = QLabel(f"Saving removes the {later_op_count} later operation(s).")
            truncation_label.setStyleSheet("color: #a15c00;")
            layout.addWidget(truncation_label)

        self._picker = PointPicker3D(
            membrane.outer.coordinates,
            membrane.outer.normals,
            np.asarray(membrane.box),
            labels,
            _label_colors(state, labels),
            pore=kind == "exclusion",
            multi_select=kind == "dai_point",
            selectable=kind != "dai_inclusion",
        )
        layout.addWidget(self._picker, stretch=1)

        form = QFormLayout()

        radius = existing_op.radius if existing_op is not None else _DEFAULT_RADIUS
        self._radius_box = FloatSpinBox(minimum=0.1, maximum=1000.0, value=radius, step=0.1, decimals=2)
        self._radius_box.valueChanged.connect(self._picker.set_radius)
        form.addRow("Radius (nm):", self._radius_box)

        self._domain_box = QComboBox()
        self._protein_box = QComboBox()
        self._leaflet_box = QComboBox()
        self._seed_note = QLabel("")
        self._seed_note.setWordWrap(True)
        self._seed_note.setStyleSheet("color: #a15c00;")

        if kind != "exclusion":
            self._add_domain_fields(form, existing_op)
        if kind == "dai_inclusion":
            self._add_protein_field(form, existing_op)

        layout.addLayout(form)
        layout.addWidget(self._seed_note)

        self._picker.set_radius(radius)
        self._update_picker_color()
        if kind == "dai_inclusion":
            self._update_inclusion_selection()
        elif existing_op is not None:
            self._picker.set_selection(list(existing_op.point_ids))

        buttons_row = QHBoxLayout()
        if existing_op is not None:
            remove_button = QPushButton("Remove")
            remove_button.clicked.connect(lambda: self.done(self.REMOVE_RESULT))
            buttons_row.addWidget(remove_button)
        buttons_row.addStretch(1)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons_row.addWidget(cancel_button)
        self._save_button = QPushButton("Save")
        mark_primary(self._save_button)
        self._save_button.clicked.connect(self._on_save_clicked)
        buttons_row.addWidget(self._save_button)
        layout.addLayout(buttons_row)

        self._picker.selection_changed.connect(self._update_save_enabled)
        self._update_save_enabled()

    def _add_domain_fields(self, form: QFormLayout, existing_op: DomainOp | None) -> None:
        for domain_id in range(self._state.domain_count):
            self._domain_box.addItem(color_icon(domain_color(self._state, domain_id)), str(domain_id), domain_id)
        default_domain = existing_op.domain_id if existing_op is not None else 1
        self._domain_box.setCurrentIndex(max(self._domain_box.findData(default_domain), 0))
        self._domain_box.currentIndexChanged.connect(self._update_picker_color)
        form.addRow("Domain id:", self._domain_box)

        self._leaflet_box.addItems(["both", "inner", "outer"])
        if existing_op is not None:
            self._leaflet_box.setCurrentText(existing_op.leaflet)
        form.addRow("Leaflet:", self._leaflet_box)

    def _add_protein_field(self, form: QFormLayout, existing_op: DomainOp | None) -> None:
        for protein in self._state.proteins:
            self._protein_box.addItem(f"{protein.name} (type {protein.type_id})", protein)
        for index, protein in enumerate(self._state.proteins):
            if existing_op is not None and protein.type_id == existing_op.protein_type_id:
                self._protein_box.setCurrentIndex(index)
        self._protein_box.currentIndexChanged.connect(self._update_inclusion_selection)
        form.addRow("Protein type:", self._protein_box)

    def result_op(self) -> DomainOp | None:
        """The DomainOp built by Save."""
        return self._result

    def _update_picker_color(self) -> None:
        if self._kind == "exclusion":
            self._picker.set_domain_color(_EXCLUSION_COLOR)
        else:
            self._picker.set_domain_color(domain_color(self._state, self._domain_box.currentData()))

    def _update_inclusion_selection(self) -> None:
        protein = self._protein_box.currentData()
        inclusions = self._membrane.inclusions.get_by_type(protein.type_id)
        self._picker.set_selection([inclusion["point_id"] for inclusion in inclusions])
        self._seed_note.setText(_UNSEEDED_PROTEIN_NOTE if protein.seed is None else "")

    def _update_save_enabled(self) -> None:
        self._save_button.setEnabled(len(self._picker.selected_point_ids()) > 0)

    def _on_save_clicked(self) -> None:
        if self._kind == "exclusion":
            self._result = DomainOp(
                kind="exclusion", radius=self._radius_box.value(), point_ids=self._picker.selected_point_ids()[:1],
            )
        elif self._kind == "dai_point":
            self._result = DomainOp(
                kind="dai_point",
                radius=self._radius_box.value(),
                leaflet=self._leaflet_box.currentText(),
                domain_id=self._domain_box.currentData(),
                point_ids=self._picker.selected_point_ids(),
            )
        else:
            self._result = DomainOp(
                kind="dai_inclusion",
                radius=self._radius_box.value(),
                leaflet=self._leaflet_box.currentText(),
                domain_id=self._domain_box.currentData(),
                protein_type_id=self._protein_box.currentData().type_id,
            )
        self.accept()
