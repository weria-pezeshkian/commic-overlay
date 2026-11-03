"""AdvancedWindow: every PLM/PCG flag not already owned by a wizard page's own widget.

Unlike CALM's Advanced window, there's very little overlap between TS2CG's
wizard pages and PLM/PCG's own flat flag list - the wizard's own values
(shape parameters, lipid ratios, protein placement) live in their own
dedicated `state.py` fields and are never part of `PLM_FIELDS`/
`PCG_FIELDS` at all (shape data is its own `[Shape Data]` section, not a
PLM/PCG command-line flag). So this window just edits `state.plm_overrides`/
`state.pcg_overrides` directly - no CALM-style write-back-to-the-owning-page
system is needed, since there's no owning page to write back to for
almost every field here.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...theme import mark_primary
from ..state import WizardState
from ..ts2cg_bridge.introspect import PCG_FIELDS, PLM_FIELDS, FieldSpec


class AdvancedWindow(QDialog):
    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self.setWindowTitle("Advanced")
        self.resize(560, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        tabs = QTabWidget()
        self._plm_getters = self._build_tab(tabs, "PLM", PLM_FIELDS, self._state.plm_overrides)
        self._pcg_getters = self._build_tab(tabs, "PCG", PCG_FIELDS, self._state.pcg_overrides)
        layout.addWidget(tabs, stretch=1)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons_row.addWidget(cancel_button)
        apply_button = QPushButton("Apply")
        mark_primary(apply_button)
        apply_button.clicked.connect(self._on_apply)
        buttons_row.addWidget(apply_button)
        layout.addLayout(buttons_row)

    def _build_tab(
        self, tabs: QTabWidget, label: str, specs: list[FieldSpec], overrides: dict[str, object]
    ) -> dict[str, tuple[FieldSpec, object]]:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        getters: dict[str, tuple[FieldSpec, object]] = {}
        for spec in specs:
            widget = self._build_field_widget(spec, overrides.get(spec.dest))
            form.addRow(QLabel(f"{spec.flag}  ({spec.help})" if spec.help else spec.flag), widget)
            getters[spec.dest] = (spec, widget)
        scroll.setWidget(form_widget)
        tabs.addTab(scroll, label)
        return getters

    @staticmethod
    def _build_field_widget(spec: FieldSpec, current: object):
        if spec.kind == "bool":
            box = QCheckBox()
            box.setChecked(bool(current) if current is not None else bool(spec.default))
            return box
        # text/int/float/choice/floats3/ints2 all round-trip through a plain QLineEdit here -
        # kept intentionally simple (no per-kind spinbox/combobox) since every value still
        # passes through TS2CG's own argv as a plain string regardless; the real CLI
        # validates it for real when it actually runs, same as CALM's own "text" fallback.
        edit = QLineEdit()
        value = current if current is not None else spec.default
        if spec.kind in ("floats3", "ints2") and isinstance(value, (list, tuple)):
            edit.setText(" ".join(str(v) for v in value))
        elif value is not None:
            edit.setText(str(value))
        edit.setPlaceholderText(f"default: {spec.default}")
        return edit

    def _on_apply(self) -> None:
        self._state.plm_overrides = self._collect(self._plm_getters)
        self._state.pcg_overrides = self._collect(self._pcg_getters)
        self.accept()

    @staticmethod
    def _collect(getters: dict[str, tuple[FieldSpec, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for dest, (spec, widget) in getters.items():
            if isinstance(widget, QCheckBox):
                if widget.isChecked():
                    result[dest] = True
                continue
            text = widget.text().strip()
            if not text:
                continue
            if spec.kind == "floats3":
                parts = text.split()
                if len(parts) == 3:
                    result[dest] = tuple(float(p) for p in parts)
            elif spec.kind == "ints2":
                parts = text.split()
                if len(parts) == 2:
                    result[dest] = tuple(int(p) for p in parts)
            elif spec.kind == "int":
                result[dest] = int(text)
            elif spec.kind == "float":
                result[dest] = float(text)
            else:
                result[dest] = text
        return result
