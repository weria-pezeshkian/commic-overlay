"""WizardState: everything the CALM wizard collects, shared across its pages and the Advanced window."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WizardState:
    working_directory: Path = field(default_factory=Path.cwd)
    structure_path: str | None = None
    trajectory_path: str | None = None
    stride: int = 1
    surface_selection: str = ""
    run_full: bool = False
    run_lipids: bool = False
    lipid_species: list[str] = field(default_factory=list)
    center_selection: str = ""
    rotate: bool = False
    remove_tmd: bool = False

    # Extra CLI flags set via the Advanced window's Apply button - only
    # ever flags no wizard page's own widget represents (e.g. --Workers,
    # --gridsize, --tmd-proximity-multiple), keyed by their own
    # FieldSpec.dest. An edit to a dest a wizard page DOES own (structure,
    # center, the lipid species list, ... - see calm_bridge/introspect.py's
    # WIZARD_STATE_DESTS) is written straight onto this same WizardState's
    # own fields above instead (advanced_window.py's
    # _write_back_wizard_fields), not kept here - so the owning page shows
    # it, correctly, the next time it's shown.
    full_overrides: dict[str, object] = field(default_factory=dict)
    lipids_overrides: dict[str, object] = field(default_factory=dict)

    # Identifies the current analyze run, stamped fresh by `app.py`'s
    # `_on_parameters_run_requested` right as Run starts. The Results page
    # tags each plot file it renders with this (so two different runs
    # never collide on the same filename) and records what it already
    # rendered for THIS run_id in `rendered_plots`, keyed by "full:<mode>"
    # or "lipids" - a click against an already-recorded plot just opens
    # that file, no rerun. A fresh run_id means an empty `rendered_plots`,
    # so a plot rendered by an earlier run is never mistaken for current.
    run_id: str = ""
    rendered_plots: dict[str, Path] = field(default_factory=dict)
