"""PlaceDomainsPage: the ordered list of circular domains and exclusions.

Each operation is recorded declaratively in `state.domain_ops`, shown as one flow-chart
button that reopens its dialog at the membrane state before it. The banner and the dialogs'
coloring replay the recorded operations against the preview point directory
(`domain_preview_math.py`).
"""

from __future__ import annotations

from typing import Any

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...theme import mark_primary
from ...widgets.point_picker_math import points_within_pore
from ..state import DomainOp, WizardState
from ..ts2cg_bridge.domain_preview_math import compute_preview_domains, undefined_domain_count
from ..ts2cg_bridge.python_tools import load_point
from .domain_op_dialog import EXCLUSION_LABEL, DomainOpDialog, color_icon, domain_color
from .preview_progress import ensure_preview

_OP_NAMES = {"dai_point": "Around point", "dai_inclusion": "Around inclusion", "exclusion": "Exclusion"}
_ADD_BUTTONS = {
    "dai_inclusion": "Add domain around inclusion",
    "dai_point": "Add domain around point",
    "exclusion": "Add exclusion",
}
_ORDER_WARNING = (
    "The order of these operations matters: they run from left to right, and a later domain "
    "paints over every earlier domain it overlaps. Click an operation to reopen it."
)
_UNSEEDED_DOP_NOTE = (
    "Distribute Domains has no fixed random seed, so the Run assigns its domains to different "
    "individual points than the ones previewed here."
)


class PlaceDomainsPage(QWidget):
    continue_requested = Signal()

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._membrane: Any = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Place domains")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        warning = QLabel(_ORDER_WARNING)
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #a15c00;")
        layout.addWidget(warning)

        self._ops_container = QWidget()
        self._ops_row = QHBoxLayout(self._ops_container)
        self._ops_row.setContentsMargins(0, 0, 0, 0)
        scroll_area = QScrollArea()
        scroll_area.setWidget(self._ops_container)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFixedHeight(64)
        layout.addWidget(scroll_area)

        self._banner_label = QLabel("")
        self._banner_label.setStyleSheet("color: #555; font-weight: 600;")
        layout.addWidget(self._banner_label)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("color: #777;")
        layout.addWidget(self._status_label)

        self._rebuild_button = QPushButton("Rebuild preview")
        self._rebuild_button.clicked.connect(self.refresh)
        self._rebuild_button.hide()
        layout.addWidget(self._rebuild_button)

        layout.addStretch(1)

        add_buttons = QHBoxLayout()
        for kind, text in _ADD_BUTTONS.items():
            button = QPushButton(text)
            button.clicked.connect(lambda _checked, k=kind: self._on_add_op(k))
            add_buttons.addWidget(button)
        add_buttons.addStretch(1)
        layout.addLayout(add_buttons)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._continue_button = QPushButton("Continue")
        mark_primary(self._continue_button)
        self._continue_button.clicked.connect(self.continue_requested)
        buttons.addWidget(self._continue_button)
        layout.addLayout(buttons)

    def refresh(self) -> None:
        self._load_preview()
        self._rebuild_ops_row()
        self._update_banner()

    def _load_preview(self) -> None:
        self._membrane = None
        self._rebuild_button.hide()
        try:
            removed = ensure_preview(self, self._state)
            self._membrane = load_point(self._state.preview_point_dir)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not a programming error
            self._status_label.setText(f"Could not build the preview: {exc}")
            self._rebuild_button.show()
            return

        notes = []
        if removed > 0:
            notes.append(f"{removed} operation(s) were removed because the settings they used have changed.")
        if self._state.dop_specs and self._state.dop_seed is None:
            notes.append(_UNSEEDED_DOP_NOTE)
        self._status_label.setText(" ".join(notes))

    def _rebuild_ops_row(self) -> None:
        while self._ops_row.count() > 0:
            item = self._ops_row.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        for index, op in enumerate(self._state.domain_ops):
            if index > 0:
                self._ops_row.addWidget(QLabel("→"))
            self._ops_row.addWidget(self._op_button(index, op))
        self._ops_row.addStretch(1)

    def _op_button(self, index: int, op: DomainOp) -> QPushButton:
        target = "" if op.kind == "exclusion" else f"domain {op.domain_id}, "
        button = QPushButton(f"{index + 1}. {_OP_NAMES[op.kind]} ({target}{op.radius:g} nm)")
        if op.kind != "exclusion":
            button.setIcon(color_icon(domain_color(self._state, op.domain_id)))
        button.clicked.connect(lambda _checked, i=index: self._on_edit_op(i))
        return button

    def _update_banner(self) -> None:
        if self._membrane is None:
            self._banner_label.setText("")
            return
        try:
            domains = compute_preview_domains(self._state.preview_point_dir, self._state, self._state.domain_ops)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not a programming error
            self._banner_label.setText(f"Could not compute domain coverage: {exc}")
            return
        count = undefined_domain_count(domains, self._state.domain_count)
        self._banner_label.setText(f"{count} of {self._state.domain_count} domains still have no points assigned.")

    def _labels_before(self, ops: list[DomainOp]) -> np.ndarray:
        """Per-point labels of the outer leaflet after `ops`: domain ids, with
        `EXCLUSION_LABEL` where a pore removes the lipids."""
        domains = compute_preview_domains(self._state.preview_point_dir, self._state, ops)
        labels = domains.outer.copy()
        outer = self._membrane.outer
        for op in ops:
            if op.kind == "exclusion":
                pore = points_within_pore(outer.coordinates, outer.normals, op.point_ids[0], op.radius)
                labels[pore] = EXCLUSION_LABEL
        return labels

    def _on_add_op(self, kind: str) -> None:
        if self._membrane is None:
            QMessageBox.warning(self, "Preview not ready", "The point directory preview could not be built.")
            return
        if kind == "dai_inclusion" and not self._state.proteins:
            QMessageBox.warning(self, "No proteins", "Add a protein on the Add Proteins page first.")
            return
        labels = self._labels_before(self._state.domain_ops)
        dialog = DomainOpDialog(self._state, kind, self._membrane, labels, parent=self)
        if dialog.exec() == DomainOpDialog.DialogCode.Accepted:
            self._state.domain_ops.append(dialog.result_op())
            self._rebuild_ops_row()
            self._update_banner()

    def _on_edit_op(self, index: int) -> None:
        if self._membrane is None:
            return
        existing = self._state.domain_ops[index]
        labels = self._labels_before(self._state.domain_ops[:index])
        later_op_count = len(self._state.domain_ops) - index - 1
        dialog = DomainOpDialog(
            self._state, existing.kind, self._membrane, labels,
            existing_op=existing, later_op_count=later_op_count, parent=self,
        )
        result = dialog.exec()
        if result == DomainOpDialog.DialogCode.Accepted:
            self._state.domain_ops[index:] = [dialog.result_op()]
        elif result == DomainOpDialog.REMOVE_RESULT:
            del self._state.domain_ops[index]
        else:
            return
        self._rebuild_ops_row()
        self._update_banner()
