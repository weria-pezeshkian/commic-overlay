"""The real point directory the Place Domains page previews on.

DOP needs real per-point curvature and "Add domain around inclusion" needs real inclusion
point ids, so this builds a point directory with the PLM or `PCG -WPointDir` call and the
`INU` calls `pipeline.py` uses, into `TS2CG_build/preview_point`. It is cached by a
signature of the settings it depends on. These builds are deterministic, so ids picked on
this directory address the same points in the Run's own directory; the Run checks that
before applying them (`dai_bridge.check_points_match_preview`).

Runs synchronously through `subprocess.run`, as `libmaker_bridge.py` does for its short
TS2CG calls.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from .input_str import build_shape_only_str
from .outputs import build_dir
from .pipeline import pcg_shape_only_argv, plm_argv
from .point_placement import build_inu_argv

if TYPE_CHECKING:
    from ..state import DomainOp, ProteinSpec, WizardState

PREVIEW_DIRNAME = "preview_point"
_PREVIEW_SHAPE_STR_FILENAME = "preview_shape.str"
_OUTER_LEAFLET_FILENAME = "OuterBM.dat"


def _protein_signature(protein: ProteinSpec) -> tuple[object, ...]:
    return (
        protein.type_id, protein.gro_path, protein.radius, protein.num_proteins,
        protein.target_curvature, protein.k_factor, protein.seed,
    )


def preview_signature(state: WizardState) -> tuple[object, ...]:
    """The settings the preview depends on. The last element is the protein list; the
    elements before it decide the membrane points."""
    if state.path_choice == "analytical_shape":
        shape_signature: tuple[object, ...] = (state.shape_type, tuple(sorted(state.shape_params.items())))
    else:
        shape_signature = (state.mesh_file_path,)
    return (
        state.path_choice,
        shape_signature,
        tuple(sorted(state.plm_overrides.items())),
        tuple(sorted(state.pcg_overrides.items())),
        tuple(_protein_signature(p) for p in state.proteins),
    )


def preview_is_current(state: WizardState) -> bool:
    return (
        state.preview_point_dir is not None
        and state.preview_signature == preview_signature(state)
        and state.preview_point_dir.exists()
    )


def _default_run(argv: list[str], cwd: Path, label: str) -> None:
    result = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{label} failed (exit {result.returncode}): {detail}")


def _require_outer_leaflet(point_directory: Path, label: str) -> None:
    """PCG can crash with exit code 0 (see `pipeline.SubprocessStep`), so success is the
    file existing."""
    if not (point_directory / _OUTER_LEAFLET_FILENAME).exists():
        raise RuntimeError(f"{label} produced no {_OUTER_LEAFLET_FILENAME}.")


def build_preview_point_dir(state: WizardState, *, run: Callable[[list[str], Path, str], None] = _default_run) -> Path:
    """Returns the preview point directory for `state`'s current settings, building it if
    the cached one is stale."""
    if preview_is_current(state):
        assert state.preview_point_dir is not None
        return state.preview_point_dir

    working_dir = Path(state.working_directory)
    build_directory = build_dir(working_dir)
    build_directory.mkdir(parents=True, exist_ok=True)
    preview_dir = build_directory / PREVIEW_DIRNAME
    if preview_dir.exists():
        shutil.rmtree(preview_dir)

    if state.path_choice == "analytical_shape":
        produced = working_dir / "point"
        if produced.exists():
            shutil.rmtree(produced)
        shape_str_path = build_directory / _PREVIEW_SHAPE_STR_FILENAME
        shape_str_path.write_text(build_shape_only_str(state))
        label = "Build preview point directory (PCG)"
        run(pcg_shape_only_argv(state, shape_str_path), working_dir, label)
        _require_outer_leaflet(produced, label)
        shutil.move(str(produced), str(preview_dir))
    else:
        label = "Build preview point directory (PLM)"
        run(plm_argv(state, preview_dir), working_dir, label)
        _require_outer_leaflet(preview_dir, label)

    for protein in state.proteins:
        run(build_inu_argv(str(preview_dir), protein), working_dir, f"Place preview protein {protein.name}")

    state.preview_point_dir = preview_dir
    state.preview_signature = preview_signature(state)
    return preview_dir


def _op_still_applies(op: DomainOp, points_changed: bool, protein_types: set[int], domain_count: int) -> bool:
    if op.kind == "dai_inclusion":
        return op.protein_type_id in protein_types and op.domain_id < domain_count
    if points_changed:
        return False
    return op.kind == "exclusion" or op.domain_id < domain_count


def prune_domain_ops(state: WizardState, previous_signature: tuple[object, ...] | None = None) -> int:
    """Removes every op the current settings can no longer apply and returns how many: ops
    on a domain beyond `state.domain_count`, ops on a removed protein, and, when
    `previous_signature` shows the membrane points changed since, ops holding point ids."""
    points_changed = previous_signature is not None and previous_signature[:-1] != preview_signature(state)[:-1]
    protein_types = {p.type_id for p in state.proteins}
    kept = [op for op in state.domain_ops if _op_still_applies(op, points_changed, protein_types, state.domain_count)]
    removed = len(state.domain_ops) - len(kept)
    state.domain_ops = kept
    return removed
