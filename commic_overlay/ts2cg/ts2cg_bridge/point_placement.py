"""Placing protein inclusions onto a TS2CG point directory, the `input.str`
`[Protein List]` entry each placed protein needs alongside it, and where PCG puts the
protein's beads relative to the membrane.

One `INU` call per added protein (`state.py`'s `ProteinSpec`), each with its own
`--protein-type` id. Successive calls edit the same point directory in place, so
`ts2cg_bridge/pipeline.py` runs them one after another.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from ..state import ProteinSpec, WizardState
from .introspect import PLM_FIELDS
from .python_tools import load_point, python_tool_argv

_PLM_DEFAULT_THICKNESS = next(f.default for f in PLM_FIELDS if f.dest == "bilayerThickness")
_SHAPES_WITH_DL = ("Sphere", "Cylinder")  # the analytical shapes whose point makers read `DL`


def bilayer_thickness(state: WizardState) -> float:
    """The membrane thickness (nm) in effect for this run: the analytical shape's Thickness,
    or PLM's `-bilayerThickness` (the override, else PLM's default) on the mesh-file path."""
    if state.path_choice == "analytical_shape":
        thickness = state.shape_params.get("Thickness")
        if isinstance(thickness, int | float):
            return float(thickness)
    override = state.plm_overrides.get("bilayerThickness")
    if isinstance(override, int | float):
        return float(override)
    return float(_PLM_DEFAULT_THICKNESS)


def outer_leaflet_height(state: WizardState) -> float:
    """Distance (nm) from the membrane midplane to the outer leaflet's points, along the
    normal: half the thickness (PLM's `H`, the shapes' `Thickness/2`), plus `DL` for a Sphere
    or Cylinder, whose point makers shift each point by `DL` along its own normal."""
    height = bilayer_thickness(state) / 2
    if state.path_choice == "analytical_shape" and state.shape_type in _SHAPES_WITH_DL:
        dl = state.shape_params.get("DL")
        if isinstance(dl, int | float):
            height += float(dl)
    return height


def placed_protein_positions(positions: np.ndarray, outer_height: float, z0: float) -> np.ndarray:
    """`positions` (nm, one row per bead) as PCG places them on a flat stretch of membrane
    whose midplane is z = 0. PCG centers the structure on its unweighted center of geometry
    (`GroFile::ReadGroFile`), then puts that center at the inclusion's outer-leaflet point
    plus `z0` along the point's normal (`BackMap::GenProtein`, `Pos + Normal*Z0`)."""
    return positions - positions.mean(axis=0) + np.array([0.0, 0.0, outer_height + z0])


def build_inu_argv(point_dir: str, protein: ProteinSpec) -> list[str]:
    """`INU` argv for one protein's own scatter placement.

    Overwrites `point_dir` in place with `--no-backup`, so a later protein's `INU` call
    builds on the same freshly built directory.
    """
    argv = python_tool_argv(
        "INU",
        "--point-dir", point_dir,
        "--protein-type", str(protein.type_id),
        "--radius", str(protein.radius),
        "--num-proteins", str(protein.num_proteins),
        "--k-factor", str(protein.k_factor),
        "--no-backup",
    )
    if protein.target_curvature is not None:
        argv.extend(["--curvature", str(protein.target_curvature)])
    if protein.seed is not None:
        argv.extend(["--seed", str(protein.seed)])
    return argv


def check_protein_count(
    point_dir: Path, protein: ProteinSpec, *, load: Callable[[Path], Any] = load_point
) -> None:
    """Raises RuntimeError unless `point_dir` holds all `protein.num_proteins` inclusions of
    `protein`'s type. INU stops early, with only a logged warning, once no point is left
    `radius` away from every protein already placed."""
    placed = len(load(point_dir).inclusions.get_by_type(protein.type_id))
    if placed < protein.num_proteins:
        raise RuntimeError(
            f"Only {placed} of {protein.num_proteins} {protein.name} proteins (type {protein.type_id}) "
            f"fit with {protein.radius:g} nm between protein centers. Lower the distance or the "
            "number of proteins on Add Proteins, or enlarge the membrane."
        )


def protein_list_line(protein: ProteinSpec) -> str:
    """One `input.str` `[Protein List]` line for `protein`: `ProteinName ID Ratio Phi Theta Z0`.
    `Z0` is measured from the outer leaflet's point (see `placed_protein_positions`).

    Phi/Theta are always written as `0` - parsed by PCG's own reader
    (`BackMap.cpp`'s `FindProteinList`) but not visibly used anywhere in
    its actual placement transform in this TS2CG version (see the plan's
    own verified-facts note on this), so there's nothing meaningful to set
    them to; `0 0` matches every worked example in TS2CG's own README and
    tutorials.
    """
    return f"{protein.name} {protein.type_id} {protein.ratio} 0 0 {protein.z0}"
