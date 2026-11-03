"""WizardState: everything the TS2CG wizard collects, shared across its pages and the Advanced window."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class ProteinSpec:
    """One added protein 'type': its own structure file, INU placement fields, and the
    `[Protein List]` entry it becomes in `input.str` (see `ts2cg_bridge/input_str.py`).

    `type_id` is both the inclusion type id INU places points under
    (`--protein-type`) and the `[Protein List]` `ID` field PCG matches
    those points back against - the two have to agree or PCG's own
    `CheckProteinInfo` rejects the run. `ratio` (the README's
    "Surface_Coverage") is collected and always written even though the
    INU-based placement path never reads it at runtime - PCG's own
    `[Protein List]` parser requires the line regardless (`BackMap.cpp`'s
    6-field check), and the field only matters if a point directory ever
    reaches PCG with no inclusions at all (not a path this wizard takes,
    but the file format doesn't know that). `z0` is the real depth
    mechanism (nm, along the local membrane normal at each inclusion's
    point) - not a `.gro` coordinate edit.
    """

    type_id: int
    name: str
    gro_path: str
    radius: float = 1.0
    num_proteins: int = 1
    target_curvature: float | None = None
    k_factor: float = 1.0
    seed: int | None = None
    ratio: float = 0.0
    z0: float = 0.0


@dataclass
class DopSpec:
    """One row of DOP's `--lipid-specs` file: `percentage` of each leaflet's points compete
    for `domain_id` with a preferred `curvature`. `DomainLipid` rows decide which lipids
    PCG places in a domain.
    """

    domain_id: int
    percentage: float = 0.0
    curvature: float = 0.0


@dataclass
class DomainOp:
    """One recorded Place Domains operation.

    `kind="dai_point"`: paints a circular patch (`radius`, `leaflet`, `domain_id`) around
    `point_ids`, which index the outer leaflet.
    `kind="dai_inclusion"`: the same around every inclusion of `protein_type_id`.
    `kind="exclusion"`: a pore of `radius` around `point_ids[0]`, on both leaflets.

    `ts2cg_bridge/dai_bridge.py` applies these.
    """

    kind: Literal["dai_point", "dai_inclusion", "exclusion"]
    radius: float = 1.0
    leaflet: str = "both"  # "both" | "inner" | "outer"
    domain_id: int = 1
    point_ids: list[int] = field(default_factory=list)
    protein_type_id: int | None = None
    path_distance: bool = False
    edge_cutoff: float = 5.0


@dataclass
class DomainLipid:
    """One lipid's row in one domain's Sort Lipids table. `area_per_lipid` is in nm²; the
    Sort Lipids page fills it from `ts2cg_bridge/apl_estimate.py`.
    """

    name: str
    ratio_up: float = 0.5
    ratio_down: float = 0.5
    area_per_lipid: float = 0.6


@dataclass
class WizardState:
    working_directory: Path = field(default_factory=Path.cwd)

    # Choose your path
    path_choice: str = ""  # "analytical_shape" | "mesh_file"

    # Analytical shape page
    shape_type: str = ""  # "Flat" | "Sphere" | "Cylinder" | "1D_PBC_Fourier"
    shape_params: dict[str, object] = field(default_factory=dict)

    # Mesh file page
    mesh_file_path: str = ""

    # Select lipids page
    lipidome_cache_dir: Path | None = None
    selected_lipids: list[str] = field(default_factory=list)
    custom_itp_paths: list[str] = field(default_factory=list)
    # lipid name -> its own source itp file (fetched lipidome + custom, merged) - kept in
    # sync by select_lipids_page.py itself, so the Run pipeline can build the .LIB file
    # directly from this without re-fetching or re-indexing anything.
    lipid_to_itp: dict[str, Path] = field(default_factory=dict)

    # Number of domains page
    domain_count: int = 1

    # Distribute domains page (DOP), which assigns points to domains (see DopSpec).
    # Continuing from this page raises domain_count to cover every domain_id referenced.
    dop_specs: list[DopSpec] = field(default_factory=list)
    dop_k_factor: float = 1.0
    dop_leaflet: str = "both"  # "both" | "inner" | "outer"
    dop_area_weighted: bool = False
    dop_seed: int | None = None

    # Sort lipids page - domain index -> that domain's own lipid rows
    domain_lipids: dict[int, list[DomainLipid]] = field(default_factory=dict)

    # domain index -> every lipid name ever offered to that domain (whether still
    # present or explicitly removed via the table's own "Delete row" button) - lets a refresh's
    # row-sync tell "already offered, deliberately removed, don't re-add" apart from
    # "newly selected since this domain was last visited, do add" (see
    # sort_lipids_page.py's own _sync_domain_rows - without this, removing a lipid
    # would be silently undone by the very refresh() the removal itself triggers).
    domain_known_lipids: dict[int, set[str]] = field(default_factory=dict)

    # Add protein page(s)
    proteins: list[ProteinSpec] = field(default_factory=list)

    # Place domains page (DAI + exclusions) - recorded in order, see DomainOp's own
    # docstring. Per-domain colors for the point-picker and Sort Lipids, assigned on first
    # use by `domain_op_dialog.domain_color`.
    domain_ops: list[DomainOp] = field(default_factory=list)
    domain_colors: dict[int, str] = field(default_factory=dict)  # domain id -> "#rrggbb"

    # Cached point directory the Place Domains page previews on
    # (ts2cg_bridge/preview_membrane.py). `preview_signature` holds the settings it was
    # last built from; a mismatch means it needs rebuilding.
    preview_point_dir: Path | None = None
    preview_signature: tuple[object, ...] | None = None

    # Summary page
    add_wall_beads: bool = False
    plm_overrides: dict[str, object] = field(default_factory=dict)
    pcg_overrides: dict[str, object] = field(default_factory=dict)
    sol_overrides: dict[str, object] = field(default_factory=dict)

    # Identifies the current build run, stamped fresh when Run starts -
    # same purpose as calm/state.py's own run_id (keeps a stale run's
    # output from being mistaken for the current one).
    run_id: str = ""
