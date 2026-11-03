"""Tests for ts2cg_bridge/preview_membrane.py - a stubbed `run`, no real TS2CG call."""

from __future__ import annotations

from pathlib import Path

import pytest

from commic_overlay.ts2cg.state import DomainOp, ProteinSpec, WizardState
from commic_overlay.ts2cg.ts2cg_bridge.outputs import build_dir
from commic_overlay.ts2cg.ts2cg_bridge.preview_membrane import (
    PREVIEW_DIRNAME,
    build_preview_point_dir,
    preview_is_current,
    preview_signature,
    prune_domain_ops,
)


class _RecordingRun:
    """Records each call and creates the output the real PLM/PCG call would."""

    def __init__(self, produce_output: bool = True) -> None:
        self.tools: list[str] = []
        self.produce_output = produce_output

    def __call__(self, argv: list[str], cwd: Path, label: str) -> None:
        tool = "INU" if "INU" in argv else argv[1]
        self.tools.append(tool)
        if not self.produce_output:
            return
        if tool == "PLM":
            out_dir = Path(argv[argv.index("-o") + 1])
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / "OuterBM.dat").write_text("")
        elif tool == "PCG":
            (cwd / "point").mkdir(parents=True, exist_ok=True)
            (cwd / "point" / "OuterBM.dat").write_text("")


def _state_mesh(tmp_path: Path) -> WizardState:
    state = WizardState()
    state.working_directory = tmp_path
    state.path_choice = "mesh_file"
    state.mesh_file_path = str(tmp_path / "shape.tsi")
    return state


def _state_analytical(tmp_path: Path) -> WizardState:
    state = WizardState()
    state.working_directory = tmp_path
    state.path_choice = "analytical_shape"
    state.shape_type = "Flat"
    state.shape_params = {"Box": (10.0, 10.0, 10.0), "Thickness": 3.8}
    return state


def _protein(type_id: int = 1) -> ProteinSpec:
    return ProteinSpec(type_id=type_id, name="STxB", gro_path="stxb.gro")


def test_build_preview_point_dir_mesh_path_runs_plm(tmp_path: Path) -> None:
    run = _RecordingRun()
    state = _state_mesh(tmp_path)
    result = build_preview_point_dir(state, run=run)
    assert result == build_dir(tmp_path) / PREVIEW_DIRNAME
    assert run.tools == ["PLM"]
    assert state.preview_point_dir == result
    assert state.preview_signature == preview_signature(state)
    assert preview_is_current(state)


def test_build_preview_point_dir_analytical_path_runs_pcg_and_moves_point_dir(tmp_path: Path) -> None:
    run = _RecordingRun()
    result = build_preview_point_dir(_state_analytical(tmp_path), run=run)
    assert run.tools == ["PCG"]
    assert (result / "OuterBM.dat").exists()
    assert not (tmp_path / "point").exists()


def test_build_preview_point_dir_clears_a_leftover_point_dir_first(tmp_path: Path) -> None:
    leftover = tmp_path / "point"
    leftover.mkdir()
    (leftover / "stale.dat").write_text("")
    result = build_preview_point_dir(_state_analytical(tmp_path), run=_RecordingRun())
    assert not (result / "stale.dat").exists()


def test_build_preview_point_dir_reports_pcg_exiting_cleanly_without_output(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="OuterBM.dat"):
        build_preview_point_dir(_state_analytical(tmp_path), run=_RecordingRun(produce_output=False))


def test_build_preview_point_dir_runs_inu_per_protein(tmp_path: Path) -> None:
    run = _RecordingRun()
    state = _state_mesh(tmp_path)
    state.proteins = [_protein()]
    build_preview_point_dir(state, run=run)
    assert run.tools == ["PLM", "INU"]


def test_build_preview_point_dir_reuses_cache_when_signature_unchanged(tmp_path: Path) -> None:
    run = _RecordingRun()
    state = _state_mesh(tmp_path)
    build_preview_point_dir(state, run=run)
    build_preview_point_dir(state, run=run)
    assert run.tools == ["PLM"]


def test_build_preview_point_dir_rebuilds_when_proteins_change(tmp_path: Path) -> None:
    run = _RecordingRun()
    state = _state_mesh(tmp_path)
    build_preview_point_dir(state, run=run)
    state.proteins = [_protein()]
    build_preview_point_dir(state, run=run)
    assert run.tools == ["PLM", "PLM", "INU"]


def test_changing_an_advanced_override_makes_the_preview_stale(tmp_path: Path) -> None:
    state = _state_mesh(tmp_path)
    build_preview_point_dir(state, run=_RecordingRun())
    state.plm_overrides = {"Mashno": 2}
    assert not preview_is_current(state)


def test_prune_keeps_applicable_ops(tmp_path: Path) -> None:
    state = _state_mesh(tmp_path)
    state.domain_count = 3
    state.proteins = [_protein(type_id=1)]
    state.domain_ops = [
        DomainOp(kind="dai_point", domain_id=2, point_ids=[1]),
        DomainOp(kind="dai_inclusion", domain_id=1, protein_type_id=1),
        DomainOp(kind="exclusion", point_ids=[4]),
    ]
    assert prune_domain_ops(state) == 0
    assert len(state.domain_ops) == 3


def test_prune_removes_ops_on_a_domain_beyond_the_domain_count(tmp_path: Path) -> None:
    state = _state_mesh(tmp_path)
    state.domain_count = 2
    state.domain_ops = [
        DomainOp(kind="dai_point", domain_id=2, point_ids=[1]),
        DomainOp(kind="exclusion", point_ids=[4]),
    ]
    assert prune_domain_ops(state) == 1
    assert [op.kind for op in state.domain_ops] == ["exclusion"]


def test_prune_removes_inclusion_ops_on_a_removed_protein(tmp_path: Path) -> None:
    state = _state_mesh(tmp_path)
    state.domain_count = 2
    state.domain_ops = [DomainOp(kind="dai_inclusion", domain_id=1, protein_type_id=1)]
    assert prune_domain_ops(state) == 1


def test_prune_removes_point_ops_when_the_membrane_points_changed(tmp_path: Path) -> None:
    state = _state_analytical(tmp_path)
    state.domain_count = 2
    state.proteins = [_protein(type_id=1)]
    previous = preview_signature(state)
    state.shape_params = {"Box": (20.0, 20.0, 20.0), "Thickness": 3.8}
    state.domain_ops = [
        DomainOp(kind="dai_point", domain_id=1, point_ids=[1]),
        DomainOp(kind="exclusion", point_ids=[4]),
        DomainOp(kind="dai_inclusion", domain_id=1, protein_type_id=1),
    ]
    assert prune_domain_ops(state, previous) == 2
    assert [op.kind for op in state.domain_ops] == ["dai_inclusion"]


def test_prune_keeps_point_ops_when_only_the_protein_list_changed(tmp_path: Path) -> None:
    state = _state_analytical(tmp_path)
    state.domain_count = 2
    previous = preview_signature(state)
    state.proteins = [_protein()]
    state.domain_ops = [DomainOp(kind="dai_point", domain_id=1, point_ids=[1])]
    assert prune_domain_ops(state, previous) == 0
