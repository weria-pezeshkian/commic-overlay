"""In-process replay of DOP and Place Domains operations, for the Place Domains page's
banner, the point-picker's domain colors and the domains Sort Lipids shows.

Replays against a fresh, unsaved load of the cached preview point directory.
`apply_circular_op` is the same function the Run applies. DOP calls TS2CG's own
`assign_domains`; with no fixed seed, its random draw differs between this preview and the
Run, as do the positions of proteins placed with no fixed seed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from .dai_bridge import apply_circular_op
from .python_tools import load_point

if TYPE_CHECKING:
    from ..state import DomainOp, WizardState


@dataclass(frozen=True)
class PreviewDomains:
    outer: np.ndarray
    inner: np.ndarray | None  # None for a monolayer


def _default_assign_domains(
    membrane: Any, lipids: list[Any], leaflet: str, k_factor: float, area_weighted: bool, seed: int | None
) -> None:
    from TS2CG.tools.domain_placer import assign_domains

    assign_domains(membrane, lipids, leaflet, k_factor, area_weighted, seed)


def _default_lipid_spec(domain_id: int, percentage: float, curvature: float) -> Any:
    from TS2CG.tools.domain_placer import LipidSpec

    return LipidSpec(
        domain_id=domain_id, name=f"domain{domain_id}", percentage=percentage, curvature=curvature, density=1.0
    )


def compute_preview_domains(
    preview_point_dir: Path,
    state: WizardState,
    ops: list[DomainOp],
    *,
    load: Callable[[Path], Any] = load_point,
    assign_domains: Callable[..., None] = _default_assign_domains,
    apply_op: Callable[[Any, DomainOp], None] = apply_circular_op,
    lipid_spec: Callable[[int, float, float], Any] = _default_lipid_spec,
) -> PreviewDomains:
    """Replays `state.dop_specs`, then every non-exclusion op of `ops` in order, against a
    fresh load of `preview_point_dir`."""
    membrane = load(preview_point_dir)

    if state.dop_specs:
        lipids = [lipid_spec(s.domain_id, s.percentage, s.curvature) for s in state.dop_specs]
        assign_domains(membrane, lipids, state.dop_leaflet, state.dop_k_factor, state.dop_area_weighted, state.dop_seed)

    for op in ops:
        if op.kind != "exclusion":
            apply_op(membrane, op)

    inner_ids = None if membrane.monolayer else np.asarray(membrane.inner.domain_ids)
    return PreviewDomains(outer=np.asarray(membrane.outer.domain_ids), inner=inner_ids)


def domain_point_shares(domains: PreviewDomains) -> dict[int, tuple[float, float | None]]:
    """Domain id -> (fraction of outer-leaflet points, fraction of inner-leaflet points, or
    None for a monolayer), for every domain id with at least one point."""
    outer_ids, outer_counts = np.unique(domains.outer, return_counts=True)
    outer = dict(zip(outer_ids.tolist(), (outer_counts / len(domains.outer)).tolist(), strict=True))
    inner: dict[int, float] = {}
    if domains.inner is not None:
        inner_ids, inner_counts = np.unique(domains.inner, return_counts=True)
        inner = dict(zip(inner_ids.tolist(), (inner_counts / len(domains.inner)).tolist(), strict=True))
    return {
        domain_id: (outer.get(domain_id, 0.0), None if domains.inner is None else inner.get(domain_id, 0.0))
        for domain_id in sorted(outer.keys() | inner.keys())
    }


def undefined_domain_count(domains: PreviewDomains, domain_count: int) -> int:
    """How many domain ids in `range(domain_count)` have zero points on both leaflets."""
    present = set(np.unique(domains.outer).tolist())
    if domains.inner is not None:
        present |= set(np.unique(domains.inner).tolist())
    return sum(1 for d in range(domain_count) if d not in present)
