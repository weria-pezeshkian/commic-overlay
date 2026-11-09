"""ParametersPage: center/rotate/remove-tmd, plus Save config, Advanced and Continue (to the
Run page)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ...theme import mark_primary
from ...widgets.config_dialogs import ask_config_save_path
from ..calm_bridge import outputs
from ..calm_bridge.introspect import field_specs, full_command_spec, lipids_command_spec
from ..calm_bridge.runner import build_argv
from ..calm_bridge.system import default_worker_count
from ..config import TOOL, save_config
from ..state import WizardState


def _labeled_checkbox(title: str, description: str) -> tuple[QCheckBox, QWidget]:
    """A checkbox plus a short, visible (not hover-only) description underneath it."""
    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 0, 0, 0)
    container_layout.setSpacing(2)

    checkbox = QCheckBox(title)
    container_layout.addWidget(checkbox)

    description_label = QLabel(description)
    description_label.setWordWrap(True)
    description_label.setStyleSheet("color: #777; font-size: 12px; margin-left: 22px;")
    container_layout.addWidget(description_label)

    return checkbox, container


class ParametersPage(QWidget):
    """Optional Parameters + Advanced/Continue.

    Continue always passes `--clear` to whichever CALM command(s) it's
    about to launch - see `calm_bridge/outputs.py`'s own docstring for why
    - and, before building anything, warns (Ok/Cancel) if the relevant
    `CALM_full`/`CALM_lipids` output directory already holds something
    from an earlier run that's about to be overwritten. The run itself
    happens on the dedicated Run page this hands off to - never here; if
    both `full` and `lipids` are selected, that page runs them
    concurrently (`ParallelCommandRunner`), so each one's own `--Workers`
    is already halved here to avoid the two together oversubscribing the
    machine's real core count.
    """

    run_requested = Signal(list)  # list[tuple[label, argv, cwd]] - see calm_bridge/runner.py
    advanced_requested = Signal()

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Optional Parameters")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        center_row = QHBoxLayout()
        center_row.addWidget(QLabel("Centering selection:"))
        self._center_edit = QLineEdit()
        self._center_edit.setPlaceholderText("optional, e.g. protein")
        self._center_edit.textChanged.connect(self._on_center_changed)
        center_row.addWidget(self._center_edit)
        layout.addLayout(center_row)

        self._rotate_check, rotate_widget = _labeled_checkbox(
            "Rotate",
            "Keeps a chosen reference direction fixed across frames, so an asymmetric "
            "feature (e.g. a bump caused by an embedded protein) stays in a consistent "
            "orientation when averaging over the whole trajectory, instead of smearing "
            "out as the membrane itself turns frame to frame.",
        )
        self._rotate_check.setToolTip("Requires a centering selection.")
        layout.addWidget(rotate_widget)

        self._remove_tmd_check, remove_tmd_widget = _labeled_checkbox(
            "Remove TMD",
            "Flags grid points too close to the embedded protein (the centering "
            "selection) as unsupported, instead of letting the surface fit silently "
            "extrapolate a guess through the region the protein actually occupies.",
        )
        self._remove_tmd_check.setToolTip("Requires a centering selection.")
        layout.addWidget(remove_tmd_widget)

        layout.addStretch(1)

        self._save_status = QLabel()
        self._save_status.setStyleSheet("color: #555;")
        self._save_status.setWordWrap(True)
        layout.addWidget(self._save_status)

        buttons_row = QHBoxLayout()
        save_button = QPushButton("Save config")
        save_button.setToolTip("Saves every step's settings to a file Load config on Working Directory reads back.")
        save_button.clicked.connect(self._on_save_config)
        buttons_row.addWidget(save_button)
        buttons_row.addStretch(1)
        advanced_button = QPushButton("Advanced")
        advanced_button.clicked.connect(self.advanced_requested)
        buttons_row.addWidget(advanced_button)
        continue_button = QPushButton("Continue")
        mark_primary(continue_button)
        continue_button.clicked.connect(self._on_continue_clicked)
        buttons_row.addWidget(continue_button)
        layout.addLayout(buttons_row)

    def refresh(self) -> None:
        """Re-syncs center/rotate/remove-tmd from self._state - call each time this page
        is shown, so an edit made elsewhere (the Advanced window) shows up here too, not
        just a value set through this page's own widgets."""
        self._center_edit.blockSignals(True)
        self._center_edit.setText(self._state.center_selection)
        self._center_edit.blockSignals(False)
        self._rotate_check.setChecked(self._state.rotate)
        self._remove_tmd_check.setChecked(self._state.remove_tmd)
        self._update_gating()

    def _on_center_changed(self, text: str) -> None:
        self._state.center_selection = text
        self._update_gating()

    def _update_gating(self) -> None:
        has_center = bool(self._center_edit.text().strip())
        self._rotate_check.setEnabled(has_center)
        self._remove_tmd_check.setEnabled(has_center)
        if not has_center:
            self._rotate_check.setChecked(False)
            self._remove_tmd_check.setChecked(False)

    def _store_fields(self) -> None:
        self._state.center_selection = self._center_edit.text().strip()
        self._state.rotate = self._rotate_check.isChecked()
        self._state.remove_tmd = self._remove_tmd_check.isChecked()

    def _on_save_config(self) -> None:
        self._store_fields()
        path = ask_config_save_path(self, self._state.working_directory, TOOL)
        if path is None:
            return
        try:
            save_config(self._state, path)
        except OSError as exc:
            self._save_status.setText(f"Could not save the config: {exc}")
            return
        self._save_status.setText(f"Saved the config to {path}")

    def _on_continue_clicked(self) -> None:
        self._store_fields()

        working_dir = self._state.working_directory
        targets = []
        if self._state.run_full:
            targets.append(outputs.full_output_dir(working_dir))
        if self._state.run_lipids:
            targets.append(outputs.lipids_output_dir(working_dir))

        existing = [t for t in targets if outputs.output_dir_would_be_overwritten(t)]
        if existing:
            names = "\n".join(str(t) for t in existing)
            answer = QMessageBox.warning(
                self,
                "Existing results will be overwritten",
                "The following director"
                + ("y" if len(existing) == 1 else "ies")
                + f" already contain results and will be overwritten:\n\n{names}",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Ok:
                return

        self.run_requested.emit(self._build_commands())

    def _build_commands(self) -> list[tuple[list[str], str]]:
        # Extra values applied via the Advanced window (never a
        # WIZARD_STATE_DESTS dest - an edit to one of those is written
        # straight onto self._state's own fields instead, which
        # _shared_values() below already reads fresh) are layered on top
        # of the simple wizard's own values here.
        working_dir = self._state.working_directory
        cwd = str(working_dir)
        commands: list[tuple[str, list[str], str]] = []

        # Both selected -> the Run page launches them concurrently
        # (ParallelCommandRunner), so each one's own --Workers default is
        # halved here rather than each independently claiming every free
        # core and the two oversubscribing the machine together.
        concurrent_jobs = sum([self._state.run_full, self._state.run_lipids])

        if self._state.run_full:
            spec = full_command_spec()
            specs = field_specs(spec.build_parser())
            values = self._shared_values(concurrent_jobs)
            values.update(self._state.full_overrides)
            values["out"] = str(outputs.full_output_dir(working_dir))
            commands.append(("full", build_argv(spec.argv_prefix, specs, values), cwd))

        if self._state.run_lipids:
            spec = lipids_command_spec()
            specs = field_specs(spec.build_parser())
            values = self._shared_values(concurrent_jobs)
            values.update(self._state.lipids_overrides)
            values["out"] = str(outputs.lipids_output_dir(working_dir))
            values["lipids"] = list(self._state.lipid_species)
            commands.append(("lipids", build_argv(spec.argv_prefix, specs, values), cwd))

        return commands

    def _shared_values(self, concurrent_jobs: int = 1) -> dict[str, object]:
        # dest names here are CALM's own (see calm_bridge/introspect.py's
        # FieldSpec.dest for each flag) - "Step" is capitalized because
        # that's what argparse derives from "--Step" with no explicit
        # dest= override (core/argument_parser.py), not a typo. "Workers"
        # isn't a wizard-owned dest (no page exposes it) - it's seeded
        # here with a real default based on this machine's own CPU count
        # rather than leaving it unset (CALM's own CLI default is a flat,
        # unparallelized 1) - still overridable via the Advanced window,
        # since self._state.full_overrides/lipids_overrides are merged on
        # top of this dict's own values afterward (_build_commands).
        return {
            "trajectory": self._state.trajectory_path,
            "structure": self._state.structure_path,
            "index": self._state.surface_selection,
            "Step": self._state.stride,
            "center": self._state.center_selection,
            "rotate": self._state.rotate,
            "remove_tmd": self._state.remove_tmd,
            "clear": True,
            "Workers": default_worker_count(concurrent_jobs),
        }
