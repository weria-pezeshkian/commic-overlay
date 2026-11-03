"""Applying Place Domains operations, for both the preview replay and the Run.

Circular domains go through TS2CG's `assign_circular_domains`, one leaflet at a time, with
these inputs prepared for it:

- `DomainOp.point_ids` and inclusion point ids index the outer leaflet. Analytical Sphere
  and Cylinder leaflets have different point counts, so an inner center is the inner point
  nearest its outer center.
- PLM's leaflet offset can place points past the box edge, which the periodic KDTree in
  `assign_circular_domains` rejects, so coordinates are wrapped into the box for the call.

TS2CG has no exclusion tool, and `Point.save` formats radii as integers. `write_exclusions`
therefore runs after every other step that saves the point directory and writes
`ExcData.dat` itself, with the fractional radii PCG's reader parses.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from .python_tools import load_point

if TYPE_CHECKING:
    from ..state import DomainOp

_EXCLUSION_FILENAME = "ExcData.dat"


def _default_assign(membrane: Any, op: DomainOp, centers: list[int], leaflet: str) -> None:
    from TS2CG.tools.circular_domains import assign_circular_domains

    assign_circular_domains(
        membrane, op.radius, centers, op.domain_id,
        leaflet=leaflet, use_path_distance=op.path_distance, edge_cutoff=op.edge_cutoff,
    )


def nearest_point_ids(coordinates: np.ndarray, targets: np.ndarray, box: np.ndarray) -> list[int]:
    """For each row of `targets`, the index of its nearest row of `coordinates` under the
    minimum-image convention of `box`."""
    ids = []
    for target in targets:
        delta = coordinates - target
        delta -= box * np.round(delta / box)
        ids.append(int(np.argmin(np.sum(delta**2, axis=1))))
    return ids


def outer_center_ids(membrane: Any, op: DomainOp) -> list[int]:
    """The outer-leaflet point ids `op` is centered on."""
    if op.kind == "dai_inclusion":
        return [inclusion["point_id"] for inclusion in membrane.inclusions.get_by_type(op.protein_type_id)]
    return list(op.point_ids)


def _assign_on_leaflet(
    membrane: Any, leaflet_name: str, op: DomainOp, centers: list[int], assign: Callable[..., None]
) -> None:
    leaflet = getattr(membrane, leaflet_name)
    original_coordinates = leaflet.coordinates
    leaflet.coordinates = np.mod(original_coordinates, membrane.box)
    try:
        assign(membrane, op, centers, leaflet_name)
    finally:
        leaflet.coordinates = original_coordinates


def apply_circular_op(membrane: Any, op: DomainOp, *, assign: Callable[..., None] = _default_assign) -> None:
    """Paints `op`'s circular domain onto `membrane` in memory."""
    centers = outer_center_ids(membrane, op)
    if membrane.monolayer or op.leaflet in ("outer", "both"):
        _assign_on_leaflet(membrane, "outer", op, centers, assign)
    if not membrane.monolayer and op.leaflet in ("inner", "both"):
        outer_points = membrane.outer.coordinates[centers]
        inner_centers = nearest_point_ids(membrane.inner.coordinates, outer_points, membrane.box)
        _assign_on_leaflet(membrane, "inner", op, inner_centers, assign)


def apply_circular_op_to_directory(
    point_dir: Path, op: DomainOp, *, load: Callable[[Path], Any] = load_point
) -> None:
    """Paints `op`'s circular domain into the point directory `point_dir`."""
    membrane = load(point_dir)
    apply_circular_op(membrane, op)
    membrane.save(point_dir, backup=False)


def write_exclusions(point_dir: Path, ops: list[DomainOp], *, load: Callable[[Path], Any] = load_point) -> None:
    """Adds one pore per op to the exclusions `point_dir` already holds and writes them."""
    exclusions = load(point_dir).exclusions
    for op in ops:
        exclusions.add_pore(op.point_ids[0], radius=op.radius)
    rows = [f"{e['id']:12d} {e['point_id']:12d} {e['radius']:12.3f}" for e in exclusions.exclusions]
    lines = [f"< Exclusion NoExc {len(rows)} >", "< id typeid radius >", *rows]
    (Path(point_dir) / _EXCLUSION_FILENAME).write_text("\n".join(lines) + "\n")


def check_points_match_preview(
    point_dir: Path, preview_dir: Path, *, load: Callable[[Path], Any] = load_point
) -> None:
    """Raises RuntimeError unless `point_dir` has the outer leaflet that recorded point ids
    were picked on."""
    run_points = load(point_dir).outer.coordinates
    picked_points = load(preview_dir).outer.coordinates
    if run_points.shape != picked_points.shape or not np.allclose(run_points, picked_points):
        raise RuntimeError(
            "This run built different membrane points than the ones the recorded points "
            "were picked on. Reopen Place Domains and pick them again."
        )
