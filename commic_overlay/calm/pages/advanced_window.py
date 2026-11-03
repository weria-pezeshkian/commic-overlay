"""AdvancedWindow: the full real parameter form for whichever CALM command(s) are relevant.

Built from CALM's own installed argparse parsers via `calm_bridge.introspect`
- not a hand-maintained list of flags, so it can't drift out of sync with
whatever CALM version is actually installed. Every field is pre-filled
from the wizard's own collected state (or a previously-applied override,
see `_wizard_prefill`) where a corresponding flag exists; everything else
starts at CALM's own CLI default, editable - except `--clear`, pre-filled
to on for the same reason the wizard's own Run always passes it (see
`calm_bridge/outputs.py`).

This window never runs anything itself - Apply stores whatever was
changed here and closes; Run only ever happens from the main window's own
Parameters page, so there is exactly one place a CALM command actually
gets launched from.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import partial

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...theme import apply_drop_shadow
from ..calm_bridge import outputs
from ..calm_bridge.introspect import (
    EXCLUDED_FROM_ADVANCED_DESTS,
    WIZARD_STATE_DESTS,
    CommandSpec,
    FieldSpec,
    field_specs,
    full_command_spec,
    lipids_command_spec,
)
from ..calm_bridge.system import default_worker_count
from ..state import WizardState


def _wizard_prefill(state: WizardState) -> dict[str, object]:
    """dest -> value, shared across whichever command forms are open.

    WIZARD_STATE_DESTS always come from the wizard's own current state -
    always the latest value, never stale. Everything else falls back to
    whatever was applied here last time (state.full_overrides/
    lipids_overrides), so reopening this window shows what you actually
    set, not CALM's bare CLI defaults again - the per-command merge
    happens in the two call sites below, since full and lipids keep
    separate override dicts.
    """
    return {
        "trajectory": state.trajectory_path,
        "structure": state.structure_path,
        "index": state.surface_selection,
        "Step": state.stride,
        "center": state.center_selection,
        "rotate": state.rotate,
        "remove_tmd": state.remove_tmd,
        "lipids": list(state.lipid_species),
        "clear": True,
    }


def _write_back_wizard_fields(state: WizardState, values: dict[str, object]) -> None:
    """Writes whichever WIZARD_STATE_DESTS are present in `values` back onto `state`.

    Called from Apply so an edit to a wizard-owned field (structure,
    center, the lipid species list, ...) made here actually takes effect
    - WizardState is the one place each of these values lives, so the
    owning wizard page picks the new value straight up the next time it's
    shown (every page's own `refresh()` re-reads from `state`).
    """
    if "trajectory" in values:
        state.trajectory_path = str(values["trajectory"]) or None
    if "structure" in values:
        state.structure_path = str(values["structure"]) or None
    if "index" in values:
        state.surface_selection = str(values["index"])
    if "Step" in values:
        try:
            state.stride = max(1, int(values["Step"]))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            pass  # leave the wizard's own value in place rather than crash on a bad edit
    if "center" in values:
        state.center_selection = str(values["center"])
    if "rotate" in values:
        state.rotate = bool(values["rotate"])
    if "remove_tmd" in values:
        # True (bare flag) or a non-empty selection string both count as
        # "on" here - the wizard's own Remove TMD checkbox is a plain
        # boolean, with no way to express a selection distinct from
        # Center's own, so a custom string collapses to True rather than
        # being silently dropped.
        state.remove_tmd = bool(values["remove_tmd"])
    if "lipids" in values:
        state.lipid_species = list(values["lipids"])  # type: ignore[arg-type]


def _optional_flag_value(box: QCheckBox, edit: QLineEdit) -> object:
    if not box.isChecked():
        return False
    value = edit.text().strip()
    return value if value else True


class _FieldRow:
    """One FieldSpec's widget(s), plus a get_value() matching build_argv's own value-shape contract."""

    def __init__(self, spec: FieldSpec, initial: object) -> None:
        self.spec = spec
        self._widget: QWidget
        self.get_value: Callable[[], object]

        if spec.kind in ("bool", "bool_optional"):
            box = QCheckBox()
            box.setChecked(bool(initial))
            self._widget = box
            self.get_value = box.isChecked
        elif spec.kind == "choice":
            combo = QComboBox()
            combo.addItems(spec.choices or [])
            text = str(initial) if initial is not None else ""
            if text in (spec.choices or []):
                combo.setCurrentText(text)
            self._widget = combo
            self.get_value = combo.currentText
        elif spec.kind == "optional_flag_value":
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            box = QCheckBox()
            edit = QLineEdit()
            edit.setPlaceholderText("optional value")
            if initial is True:
                box.setChecked(True)
            elif isinstance(initial, str) and initial:
                box.setChecked(True)
                edit.setText(initial)
            row_layout.addWidget(box)
            row_layout.addWidget(edit)
            self._widget = row
            self.get_value = partial(_optional_flag_value, box, edit)
        elif spec.kind in ("multichoice", "multi", "append"):
            edit = QLineEdit()
            if isinstance(initial, (list, tuple)):
                edit.setText(" ".join(str(v) for v in initial))
            elif initial:
                edit.setText(str(initial))
            placeholder = "space-separated"
            if spec.choices:
                placeholder += f" ({'/'.join(spec.choices)})"
            edit.setPlaceholderText(placeholder)
            self._widget = edit
            self.get_value = lambda edit=edit: edit.text().split()
        else:  # "text"
            edit = QLineEdit()
            if initial is not None:
                edit.setText(str(initial))
            self._widget = edit
            self.get_value = edit.text

    def widget(self) -> QWidget:
        return self._widget


class _CommandForm(QWidget):
    """One command's full form (every FieldSpec, required separated from optional)."""

    def __init__(self, spec: CommandSpec, prefill: dict[str, object], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec = spec
        self.specs = field_specs(spec.build_parser())
        self._rows: dict[str, _FieldRow] = {}

        outer = QVBoxLayout(self)
        required_box = QGroupBox("Required arguments")
        required_form = QFormLayout(required_box)
        optional_box = QGroupBox("Optional arguments")
        optional_form = QFormLayout(optional_box)

        for field_spec in self.specs:
            initial = prefill.get(field_spec.dest, field_spec.default)
            row = _FieldRow(field_spec, initial)
            self._rows[field_spec.dest] = row
            label = QLabel(field_spec.flag)
            label.setToolTip(field_spec.help)
            target_form = required_form if field_spec.required else optional_form
            target_form.addRow(label, row.widget())

        outer.addWidget(required_box)
        outer.addWidget(optional_box)
        outer.addStretch(1)

        # Captured once, right after the widgets are built (so it reflects
        # the prefill as each row's own get_value() would report it, not
        # the raw prefill dict - a "Step" prefill of int 1 becomes "1" via
        # the text widget's own get_value, the same shape values() itself
        # returns later) - lets changed_wizard_state_values() below tell
        # "the user actually edited this field in THIS form" apart from
        # "this form still shows its own original, un-edited copy".
        self._initial_values = self.values()

    def values(self) -> dict[str, object]:
        return {dest: row.get_value() for dest, row in self._rows.items()}

    def changed_wizard_state_values(self) -> dict[str, object]:
        """WIZARD_STATE_DESTS entries whose current value differs from what THIS form's
        own widgets were originally pre-filled with.

        Full and Lipids each carry their own independent copy of every
        shared wizard-state field (structure, center, ...) - comparing
        against this form's own starting point, not the other form's,
        means an edit made only in one of the two forms is never
        clobbered by the other form's untouched, stale copy of the same
        field when both get applied together.
        """
        current = self.values()
        return {
            dest: current[dest]
            for dest in WIZARD_STATE_DESTS
            if dest in current and current[dest] != self._initial_values.get(dest)
        }

    def extra_values(self) -> dict[str, object]:
        """`values()`, minus every WIZARD_STATE_DESTS/EXCLUDED_FROM_ADVANCED_DESTS dest -
        the truly extra, CLI-only knobs Apply saves into the override dict."""
        excluded = WIZARD_STATE_DESTS | EXCLUDED_FROM_ADVANCED_DESTS
        return {dest: value for dest, value in self.values().items() if dest not in excluded}


class AdvancedWindow(QDialog):
    """Separate window: the full real parameter form for whichever command(s) the wizard selected.

    Apply writes any edited WIZARD_STATE_DESTS field straight back onto
    the shared WizardState (so the owning wizard page shows it too, next
    time it's shown) and saves everything else into
    `state.full_overrides`/`lipids_overrides`, then closes. Cancel
    discards whatever was typed here and closes without touching state at
    all.
    """

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Advanced parameters")
        self.resize(640, 600)
        self._state = state

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(16, 16, 16, 16)
        outer_layout.setSpacing(12)

        card = QFrame()
        card.setObjectName("advancedCard")
        card.setStyleSheet("#advancedCard { background-color: #ffffff; border-radius: 10px; }")
        apply_drop_shadow(card)
        layout = QVBoxLayout(card)
        outer_layout.addWidget(card, stretch=1)

        prefill = _wizard_prefill(state)

        self._full_form: _CommandForm | None = None
        self._lipids_form: _CommandForm | None = None
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)

        # "Workers" sits between the two layers: a real default based on
        # this machine's own CPU count (not CALM's own flat, unparallelized
        # CLI default of 1), but still overridden by a previously-applied
        # explicit value if there is one - same precedence, and the same
        # concurrent_jobs-based halving when both are selected (they run
        # concurrently - see calm_bridge/runner.py::ParallelCommandRunner),
        # that parameters_page.py's own _shared_values/_build_commands use
        # for the simple wizard's own Run.
        concurrent_jobs = sum([state.run_full, state.run_lipids])

        if state.run_full:
            full_prefill = {**prefill, "Workers": default_worker_count(concurrent_jobs), **state.full_overrides}
            full_prefill["out"] = str(outputs.full_output_dir(state.working_directory))
            self._full_form = _CommandForm(full_command_spec(), full_prefill)
            content_layout.addWidget(QLabel("analyze full"))
            content_layout.addWidget(self._full_form)

        if state.run_lipids:
            lipids_prefill = {
                **prefill,
                "Workers": default_worker_count(concurrent_jobs),
                **state.lipids_overrides,
            }
            lipids_prefill["out"] = str(outputs.lipids_output_dir(state.working_directory))
            self._lipids_form = _CommandForm(lipids_command_spec(), lipids_prefill)
            content_layout.addWidget(QLabel("analyze lipids"))
            content_layout.addWidget(self._lipids_form)

        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons_row.addWidget(cancel_button)
        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self._on_apply_clicked)
        buttons_row.addWidget(apply_button)
        layout.addLayout(buttons_row)

    def _on_apply_clicked(self) -> None:
        # Only each form's own CHANGED wizard-state fields are written
        # back (see _CommandForm.changed_wizard_state_values) - Full and
        # Lipids each carry their own independent copy of every shared
        # field (structure, center, ...), so writing back a form's full
        # values() unconditionally would let whichever form is processed
        # second clobber a genuine edit in the other with its own stale,
        # untouched copy, every time only one of the two was actually
        # edited - the common case, not an edge case.
        if self._full_form is not None:
            _write_back_wizard_fields(self._state, self._full_form.changed_wizard_state_values())
            self._state.full_overrides = self._full_form.extra_values()
        if self._lipids_form is not None:
            _write_back_wizard_fields(self._state, self._lipids_form.changed_wizard_state_values())
            self._state.lipids_overrides = self._lipids_form.extra_values()
        self.accept()
