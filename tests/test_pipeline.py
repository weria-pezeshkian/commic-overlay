"""Tests for ts2cg_bridge/pipeline.py's step list - no step is executed against real TS2CG."""

from __future__ import annotations

from pathlib import Path

from commic_overlay.ts2cg.state import DomainOp, DopSpec, ProteinSpec, WizardState
from commic_overlay.ts2cg.ts2cg_bridge.outputs import build_dir
from commic_overlay.ts2cg.ts2cg_bridge.pipeline import PythonStep, SubprocessStep, build_pipeline


def _state(tmp_path: Path) -> WizardState:
    state = WizardState()
    state.working_directory = tmp_path
    state.path_choice = "mesh_file"
    state.mesh_file_path = str(tmp_path / "shape.tsi")
    return state


def _labels(state: WizardState) -> list[str]:
    return [step.label for step in build_pipeline(state)]


def test_plain_run_has_no_domain_steps(tmp_path: Path) -> None:
    assert _labels(_state(tmp_path)) == [
        "Build point directory (PLM)",
        "Build lipid library (.LIB)",
        "Write input.str",
        "Build membrane structure (PCG)",
    ]


def test_dop_runs_after_proteins_and_before_place_domains(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.proteins = [ProteinSpec(type_id=1, name="STxB", gro_path="stxb.gro")]
    state.dop_specs = [DopSpec(domain_id=0, percentage=1.0)]
    state.domain_ops = [DomainOp(kind="dai_inclusion", domain_id=1, protein_type_id=1)]
    labels = _labels(state)
    protein = labels.index("Place protein STxB (type 1)")
    write_input = labels.index("Write domain_input.txt")
    dop = labels.index("Distribute domains (DOP)")
    domain = labels.index("Place domain 1 (dai_inclusion)")
    assert protein < write_input < dop < domain


def test_domain_input_file_is_written_when_its_step_runs(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.dop_specs = [DopSpec(domain_id=0, percentage=1.0)]
    steps = build_pipeline(state)
    domain_input = build_dir(tmp_path) / "domain_input.txt"
    assert not domain_input.exists()
    write_step = next(step for step in steps if step.label == "Write domain_input.txt")
    assert isinstance(write_step, PythonStep)
    write_step.action()
    assert domain_input.read_text() == "0 domain0 1 0 1\n"


def test_circular_ops_keep_their_order_and_exclusions_run_last(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.preview_point_dir = tmp_path / "preview"
    state.domain_ops = [
        DomainOp(kind="exclusion", point_ids=[9]),
        DomainOp(kind="dai_point", domain_id=2, point_ids=[1]),
        DomainOp(kind="dai_point", domain_id=1, point_ids=[2]),
    ]
    labels = _labels(state)
    assert labels.index("Place domain 2 (dai_point)") < labels.index("Place domain 1 (dai_point)")
    assert labels.index("Place domain 1 (dai_point)") < labels.index("Write exclusions")
    assert labels.index("Write exclusions") < labels.index("Build lipid library (.LIB)")


def test_picked_points_are_checked_before_any_domain_step(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.preview_point_dir = tmp_path / "preview"
    state.domain_ops = [DomainOp(kind="dai_point", domain_id=1, point_ids=[1])]
    labels = _labels(state)
    assert labels.index("Check picked points") < labels.index("Place domain 1 (dai_point)")


def test_inclusion_ops_need_no_picked_point_check(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.domain_ops = [DomainOp(kind="dai_inclusion", domain_id=1, protein_type_id=1)]
    assert "Check picked points" not in _labels(state)


def test_inu_and_dop_run_through_the_python_tools_launcher(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.proteins = [ProteinSpec(type_id=1, name="STxB", gro_path="stxb.gro")]
    state.dop_specs = [DopSpec(domain_id=0, percentage=1.0)]
    for step in build_pipeline(state):
        if isinstance(step, SubprocessStep) and step.label.startswith(("Place protein", "Distribute domains")):
            assert step.argv[2].endswith("python_tools.py")


def test_final_pcg_step_passes_the_point_directory_relative_to_its_cwd(tmp_path: Path) -> None:
    final_step = build_pipeline(_state(tmp_path))[-1]
    assert isinstance(final_step, SubprocessStep)
    assert final_step.cwd == str(tmp_path)
    assert final_step.argv[final_step.argv.index("-dts") + 1] == "TS2CG_point"


def test_final_pcg_step_passes_bondlength_0_2_by_default(tmp_path: Path) -> None:
    final_step = build_pipeline(_state(tmp_path))[-1]
    assert isinstance(final_step, SubprocessStep)
    assert final_step.argv[final_step.argv.index("-Bondlength") + 1] == "0.2"


def test_final_pcg_step_passes_a_bondlength_set_in_the_advanced_window(tmp_path: Path) -> None:
    state = _state(tmp_path)
    state.pcg_overrides = {"Bondlength": 0.15}
    final_step = build_pipeline(state)[-1]
    assert isinstance(final_step, SubprocessStep)
    assert final_step.argv[final_step.argv.index("-Bondlength") + 1] == "0.15"
