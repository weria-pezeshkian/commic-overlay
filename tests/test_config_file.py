"""Tests for config_file.py and the CALM and TS2CG config modules."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from commic_overlay.calm.config import load_config as load_calm_config
from commic_overlay.calm.config import run_config_path as calm_run_config_path
from commic_overlay.calm.config import save_config as save_calm_config
from commic_overlay.calm.state import WizardState as CalmState
from commic_overlay.config_file import ConfigError
from commic_overlay.ts2cg.config import load_config as load_ts2cg_config
from commic_overlay.ts2cg.config import run_config_path as ts2cg_run_config_path
from commic_overlay.ts2cg.config import save_config as save_ts2cg_config
from commic_overlay.ts2cg.state import DomainLipid, DomainOp, DopSpec, ProteinSpec
from commic_overlay.ts2cg.state import WizardState as Ts2cgState
from commic_overlay.ts2cg.ts2cg_bridge.input_str import build_input_str
from commic_overlay.ts2cg.ts2cg_bridge.preview_membrane import preview_signature


def _ts2cg_state(tmp_path: Path) -> Ts2cgState:
    state = Ts2cgState(working_directory=tmp_path / "work")
    state.path_choice = "analytical_shape"
    state.shape_type = "1D_PBC_Fourier"
    state.shape_params = {
        "Box": (20.0, 20.0, 10.0), "Thickness": 4.0, "Density": 2.5,
        "Modes": ((1.0, 1.0, 0.0), (0.5, 2.0, 90.0)),
    }
    state.lipidome_cache_dir = tmp_path / "lipidome"
    state.selected_lipids = ["POPC", "CHOL"]
    state.custom_itp_paths = [str(tmp_path / "custom.itp")]
    state.lipid_to_itp = {"POPC": tmp_path / "PC.itp", "CHOL": tmp_path / "sterols.itp"}
    state.domain_count = 2
    state.dop_specs = [DopSpec(domain_id=1, percentage=0.4, curvature=-0.1), DopSpec(domain_id=0, percentage=0.6)]
    state.dop_k_factor = 2.5
    state.dop_leaflet = "outer"
    state.dop_area_weighted = True
    state.dop_seed = 11
    state.domain_lipids = {
        0: [DomainLipid("POPC", 1.0, 1.0, 0.609)],
        1: [DomainLipid("POPC", 0.7, 0.6, 0.609), DomainLipid("CHOL", 0.3, 0.4, 0.4)],
    }
    state.domain_known_lipids = {0: {"POPC", "CHOL"}, 1: {"POPC", "CHOL"}}
    state.proteins = [
        ProteinSpec(type_id=1, name="protein1", gro_path=str(tmp_path / "P1.gro"), radius=2.0, num_proteins=3,
                    target_curvature=None, seed=4, ratio=0.01, z0=-2.0, rotation_x=26.3, rotation_y=37.2),
        ProteinSpec(type_id=2, name="protein2", gro_path=str(tmp_path / "P2.gro"), target_curvature=0.05),
    ]
    state.domain_ops = [
        DomainOp(kind="dai_point", radius=1.5, leaflet="outer", domain_id=1, point_ids=[12, 40]),
        DomainOp(kind="dai_inclusion", domain_id=1, protein_type_id=2, path_distance=True),
        DomainOp(kind="exclusion", radius=0.8, point_ids=[7]),
    ]
    state.domain_colors = {0: "#2a6fdb", 1: "#db7f2a"}
    state.add_wall_beads = True
    state.plm_overrides = {"rescalefactor": (1.0, 1.0, 2.0)}
    state.pcg_overrides = {"Bondlength": 0.2, "renorm": True}
    state.preview_signature = preview_signature(state)
    state.preview_point_dir = tmp_path / "work" / "TS2CG_build" / "preview_point"
    state.run_id = "20261109_101500_000001"
    return state


def test_ts2cg_config_round_trips_every_setting(tmp_path: Path) -> None:
    state = _ts2cg_state(tmp_path)
    path = tmp_path / "saved.json"
    save_ts2cg_config(state, path)
    loaded = load_ts2cg_config(path)
    expected = dataclasses.replace(state, preview_point_dir=None, run_id="")
    assert loaded == expected
    assert build_input_str(loaded) == build_input_str(state)


def test_ts2cg_config_keeps_the_signature_the_points_were_picked_on(tmp_path: Path) -> None:
    state = _ts2cg_state(tmp_path)
    path = tmp_path / "saved.json"
    save_ts2cg_config(state, path)
    loaded = load_ts2cg_config(path)
    assert loaded.preview_signature == preview_signature(loaded)


def test_ts2cg_config_leaves_out_the_session_only_fields(tmp_path: Path) -> None:
    path = tmp_path / "saved.json"
    save_ts2cg_config(_ts2cg_state(tmp_path), path)
    document = json.loads(path.read_text())
    assert document["tool"] == "ts2cg"
    assert document["format_version"] == 1
    assert "preview_point_dir" not in document["state"] and "run_id" not in document["state"]
    assert document["state"]["domain_lipids"]["1"][1] == {
        "name": "CHOL", "ratio_up": 0.3, "ratio_down": 0.4, "area_per_lipid": 0.4,
    }


def test_untyped_values_come_back_with_tuples(tmp_path: Path) -> None:
    state = Ts2cgState(shape_params={"Box": (10.0, 10.0, 10.0), "Modes": [(1.0, 1.0, 0.0)]})
    path = tmp_path / "saved.json"
    save_ts2cg_config(state, path)
    assert load_ts2cg_config(path).shape_params == {"Box": (10.0, 10.0, 10.0), "Modes": ((1.0, 1.0, 0.0),)}


def test_calm_config_round_trips_every_setting(tmp_path: Path) -> None:
    state = CalmState(
        working_directory=tmp_path, structure_path="/data/system.gro", trajectory_path="/data/traj.xtc", stride=5,
        surface_selection="resname POPC", run_full=True, run_lipids=True, lipid_species=["POPC", "CHOL"],
        center_selection="protein", rotate=True, remove_tmd=True,
        full_overrides={"Workers": "4", "method": ["sft", "fft"]}, lipids_overrides={"Remove_TMD": "protein"},
        run_id="x", rendered_plots={"lipids": tmp_path / "plot.png"},
    )
    path = tmp_path / "calm.json"
    save_calm_config(state, path)
    loaded = load_calm_config(path)
    expected = dataclasses.replace(
        state, run_id="", rendered_plots={}, full_overrides={"Workers": "4", "method": ("sft", "fft")}
    )
    assert loaded == expected


def test_each_tool_refuses_the_other_tools_config(tmp_path: Path) -> None:
    calm_path = tmp_path / "calm.json"
    ts2cg_path = tmp_path / "ts2cg.json"
    save_calm_config(CalmState(), calm_path)
    save_ts2cg_config(Ts2cgState(), ts2cg_path)
    with pytest.raises(ConfigError, match="not a TS2CG config: it was saved by CALM"):
        load_ts2cg_config(calm_path)
    with pytest.raises(ConfigError, match="not a CALM config: it was saved by TS2CG"):
        load_calm_config(ts2cg_path)


def test_a_field_the_file_leaves_out_keeps_its_default(tmp_path: Path) -> None:
    path = tmp_path / "partial.json"
    path.write_text(json.dumps({"tool": "ts2cg", "format_version": 1, "state": {"domain_count": 3, "unknown": 1}}))
    loaded = load_ts2cg_config(path)
    assert loaded.domain_count == 3
    assert loaded.proteins == [] and loaded.dop_k_factor == 1.0


def test_run_configs_go_into_the_working_directory_under_generic_names(tmp_path: Path) -> None:
    assert ts2cg_run_config_path(tmp_path) == tmp_path / "ts2cg_config.json"
    assert calm_run_config_path(tmp_path) == tmp_path / "calm_config.json"
