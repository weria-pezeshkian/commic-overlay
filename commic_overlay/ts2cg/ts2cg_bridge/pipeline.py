"""Orchestrating one real TS2CG run.

Builds the point directory (mesh-file path: `PLM`; analytical-shape path:
`PCG -function analytical_shape -WPointDir`, from a `[Shape Data]`-only
`input_shape.str`), places each added protein (`INU`), distributes domains
(`DOP`), applies the Place Domains operations, assembles the `.LIB` scoped
to the selected lipids, writes each rotated protein's `.gro`, writes
`input.str`, and runs `PCG -function backmap`
to build the structure. Each step edits the same point directory or reads a
previous step's output, so the steps form a strictly sequential list.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from .dai_bridge import apply_circular_op_to_directory, check_points_match_preview, write_exclusions
from .dop_bridge import DOMAIN_INPUT_FILENAME, build_dop_argv, write_domain_input_file
from .input_str import build_input_str, build_shape_only_str
from .introspect import PCG_FIELDS, PLM_FIELDS, build_argv
from .libmaker_bridge import build_lib_file
from .outputs import INPUT_STR_FILENAME, LIB_FILENAME, OUTPUT_PREFIX, build_dir, point_dir
from .point_placement import build_inu_argv, check_protein_count
from .protein_structure import is_rotated, write_rotated_structure

if TYPE_CHECKING:
    from ..state import WizardState


@dataclass
class SubprocessStep:
    """One subprocess call, run through `CommandRunner`.

    `expected_outputs`, when given, names the files this step must produce, checked after
    the subprocess exits regardless of its exit code: TS2CG's `PCG` wrapper
    (`TS2CG/cpp/base.py`) catches an internal segfault and logs it with exit code 0. A
    missing file fails the step the same way a nonzero exit code does, and `run_page.py`
    reports that failure for the user to act on.
    """

    label: str
    argv: list[str]
    cwd: str
    expected_outputs: list[Path] | None = None


@dataclass
class PythonStep:
    """A fast, synchronous, in-process step (writing a file, assembling the `.LIB`) - no
    subprocess, no live progress needed; `action` raises on failure, same as any Python
    call, caught by whoever runs the pipeline (`run_page.py`)."""

    label: str
    action: Callable[[], None]


Step = SubprocessStep | PythonStep


def build_pipeline(state: WizardState) -> list[Step]:
    working_dir = Path(state.working_directory)
    point_directory = point_dir(working_dir)
    build_directory = build_dir(working_dir)
    build_directory.mkdir(parents=True, exist_ok=True)

    steps: list[Step] = []
    steps.extend(_point_directory_steps(state, working_dir, point_directory, build_directory))
    steps.extend(_protein_placement_steps(state, working_dir, point_directory))
    steps.extend(_picked_point_check_steps(state, point_directory))
    steps.extend(_distribute_domains_steps(state, working_dir, point_directory, build_directory))
    steps.extend(_place_domains_steps(state, point_directory))
    steps.append(_build_lib_step(state, build_directory))
    steps.extend(_rotated_structure_steps(state, build_directory))
    steps.append(_write_input_str_step(state, build_directory))
    steps.append(_final_pcg_step(state, working_dir, point_directory, build_directory))
    return steps


def plm_argv(state: WizardState, point_directory: Path) -> list[str]:
    """`TS2CG PLM` argv for the mesh-file path - factored out so `preview_membrane.py`
    can build the exact same call without duplicating it."""
    plm_values: dict[str, object] = dict(state.plm_overrides)
    plm_values.setdefault("TSfile", state.mesh_file_path)
    plm_values["o"] = str(point_directory)
    return build_argv("PLM", PLM_FIELDS, plm_values)


def pcg_shape_only_argv(state: WizardState, shape_str_path: Path) -> list[str]:
    """`TS2CG PCG -function analytical_shape -WPointDir` argv for the analytical-shape
    path's first pass - factored out for the same reason as `plm_argv`. Always writes
    into a `point/` folder relative to whatever `cwd` the caller runs this in
    (`-WPointDir`'s own output name is hardcoded in TS2CG's C++ source,
    `PointBasedBlueprint.cpp:99` - it ignores `-dts` entirely for this)."""
    pcg_values: dict[str, object] = dict(state.pcg_overrides)
    pcg_values.update({"str": str(shape_str_path), "function": "analytical_shape", "WPointDir": True})
    pcg_values.pop("dts", None)
    return build_argv("PCG", PCG_FIELDS, pcg_values)


def _write_shape_str(state: WizardState, shape_str_path: Path) -> None:
    shape_str_path.write_text(build_shape_only_str(state))


def _move_point_dir_into_place(produced: Path, point_directory: Path) -> None:
    if point_directory.exists():
        shutil.rmtree(point_directory)
    shutil.move(str(produced), str(point_directory))


def _point_directory_steps(
    state: WizardState, working_dir: Path, point_directory: Path, build_directory: Path
) -> list[Step]:
    if state.path_choice == "analytical_shape":
        shape_str_path = build_directory / "input_shape.str"
        produced = working_dir / "point"
        return [
            PythonStep("Write shape definition", partial(_write_shape_str, state, shape_str_path)),
            SubprocessStep(
                "Build point directory (PCG)",
                pcg_shape_only_argv(state, shape_str_path),
                str(working_dir),
                expected_outputs=[produced / "OuterBM.dat"],
            ),
            PythonStep(
                "Move point directory into place", partial(_move_point_dir_into_place, produced, point_directory)
            ),
        ]

    return [
        SubprocessStep(
            "Build point directory (PLM)",
            plm_argv(state, point_directory),
            str(working_dir),
            expected_outputs=[point_directory / "OuterBM.dat"],
        )
    ]


def _protein_placement_steps(state: WizardState, working_dir: Path, point_directory: Path) -> list[Step]:
    steps: list[Step] = []
    for protein in state.proteins:
        argv = build_inu_argv(str(point_directory), protein)
        steps.append(SubprocessStep(f"Place protein {protein.name} (type {protein.type_id})", argv, str(working_dir)))
        steps.append(
            PythonStep(
                f"Check every protein of type {protein.type_id} fits",
                partial(check_protein_count, point_directory, protein),
            )
        )
    return steps


def _picked_point_check_steps(state: WizardState, point_directory: Path) -> list[Step]:
    if not any(op.point_ids for op in state.domain_ops):
        return []
    assert state.preview_point_dir is not None
    action = partial(check_points_match_preview, point_directory, state.preview_point_dir)
    return [PythonStep("Check picked points", action)]


def _distribute_domains_steps(
    state: WizardState, working_dir: Path, point_directory: Path, build_directory: Path
) -> list[Step]:
    """Writes DOP's `--lipid-specs` file and runs `DOP`, before any Place Domains
    operation, since DOP replaces a whole leaflet's `domain_ids`."""
    if not state.dop_specs:
        return []
    domain_input_path = build_directory / DOMAIN_INPUT_FILENAME
    argv = build_dop_argv(str(point_directory), str(domain_input_path), str(build_directory), state)
    return [
        PythonStep("Write domain_input.txt", partial(write_domain_input_file, state.dop_specs, domain_input_path)),
        SubprocessStep("Distribute domains (DOP)", argv, str(working_dir)),
    ]


def _place_domains_steps(state: WizardState, point_directory: Path) -> list[Step]:
    """One step per circular operation in recorded order, then one step writing every
    exclusion (`dai_bridge.py` explains why exclusions go last)."""
    steps: list[Step] = []
    for op in state.domain_ops:
        if op.kind != "exclusion":
            label = f"Place domain {op.domain_id} ({op.kind})"
            steps.append(PythonStep(label, partial(apply_circular_op_to_directory, point_directory, op)))
    exclusions = [op for op in state.domain_ops if op.kind == "exclusion"]
    if exclusions:
        steps.append(PythonStep("Write exclusions", partial(write_exclusions, point_directory, exclusions)))
    return steps


def _build_lib(state: WizardState, lib_path: Path) -> None:
    result = build_lib_file(state.selected_lipids, state.lipid_to_itp, lib_path)
    if result.failed_lipids:
        names = ", ".join(result.failed_lipids)
        raise RuntimeError(
            f"Could not build a .LIB entry for: {names}. libmaker's default reference "
            "bead (PO4) isn't present in these - sterols and a few other lipid "
            "categories use a different one, which this overlay doesn't yet expose a "
            "way to override. Deselect these lipids, or add a hand-built .LIB snippet "
            "for them via the Select Lipids page's Advanced popup."
        )


def _build_lib_step(state: WizardState, build_directory: Path) -> PythonStep:
    return PythonStep("Build lipid library (.LIB)", partial(_build_lib, state, build_directory / LIB_FILENAME))


def _rotated_structure_steps(state: WizardState, build_directory: Path) -> list[Step]:
    """One step per rotated protein, writing the rotated `.gro` that `input.str` includes."""
    return [
        PythonStep(
            f"Write rotated structure of protein type {protein.type_id}",
            partial(write_rotated_structure, protein, build_directory),
        )
        for protein in state.proteins
        if is_rotated(protein)
    ]


def _write_input_str(state: WizardState, input_str_path: Path) -> None:
    input_str_path.write_text(build_input_str(state))


def _write_input_str_step(state: WizardState, build_directory: Path) -> PythonStep:
    return PythonStep("Write input.str", partial(_write_input_str, state, build_directory / INPUT_STR_FILENAME))


def _final_pcg_step(
    state: WizardState, working_dir: Path, point_directory: Path, build_directory: Path
) -> SubprocessStep:
    input_str_path = build_directory / INPUT_STR_FILENAME
    lib_path = build_directory / LIB_FILENAME
    pcg_values: dict[str, object] = dict(state.pcg_overrides)
    pcg_values.update(
        {
            # Relative to this step's cwd: PCG prefixes `-dts` with "./" (ReadDTSFolder.cpp).
            "dts": os.path.relpath(point_directory, working_dir),
            "str": str(input_str_path),
            "defout": str(build_directory / OUTPUT_PREFIX),
            "LLIB": str(lib_path),
            "function": "backmap",
            "Wall": bool(state.add_wall_beads),
        }
    )
    return SubprocessStep(
        "Build membrane structure (PCG)",
        build_argv("PCG", PCG_FIELDS, pcg_values),
        str(working_dir),
        expected_outputs=[build_directory / f"{OUTPUT_PREFIX}.gro", build_directory / f"{OUTPUT_PREFIX}.top"],
    )
