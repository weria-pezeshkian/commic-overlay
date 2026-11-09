"""Tests for ts2cg_bridge/point_placement.py."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from commic_overlay.ts2cg.state import ProteinSpec, WizardState
from commic_overlay.ts2cg.ts2cg_bridge.point_placement import (
    build_inu_argv,
    check_protein_count,
    outer_leaflet_height,
    placed_protein_positions,
    protein_list_line,
)


def _protein(**overrides: object) -> ProteinSpec:
    defaults: dict[str, object] = {"type_id": 1, "name": "STxB", "gro_path": "stxb.gro"}
    defaults.update(overrides)
    return ProteinSpec(**defaults)


def test_build_inu_argv_includes_required_fields() -> None:
    protein = _protein(radius=1.5, num_proteins=4, k_factor=2.0)
    argv = build_inu_argv("point", protein)
    assert argv[3] == "INU"
    assert "--point-dir" in argv and argv[argv.index("--point-dir") + 1] == "point"
    assert "--protein-type" in argv and argv[argv.index("--protein-type") + 1] == "1"
    assert "--radius" in argv and argv[argv.index("--radius") + 1] == "1.5"
    assert "--num-proteins" in argv and argv[argv.index("--num-proteins") + 1] == "4"
    assert "--k-factor" in argv and argv[argv.index("--k-factor") + 1] == "2.0"
    assert "--no-backup" in argv


def test_build_inu_argv_omits_optional_curvature_and_seed_by_default() -> None:
    argv = build_inu_argv("point", _protein())
    assert "--curvature" not in argv
    assert "--seed" not in argv


def test_build_inu_argv_includes_curvature_and_seed_when_set() -> None:
    protein = _protein(target_curvature=0.05, seed=42)
    argv = build_inu_argv("point", protein)
    assert argv[argv.index("--curvature") + 1] == "0.05"
    assert argv[argv.index("--seed") + 1] == "42"


def test_protein_list_line_formats_name_id_ratio_phi_theta_z0() -> None:
    protein = _protein(type_id=3, name="STxB", ratio=0.5, z0=-1.1)
    assert protein_list_line(protein) == "STxB 3 0.5 0 0 -1.1"


def test_protein_list_line_matches_readme_worked_example() -> None:
    # The exact line from TS2CG-v2.0/README.md's own input.str example.
    protein = ProteinSpec(type_id=1, name="STxB", gro_path="stxb.gro", ratio=0.5, z0=-1.1)
    assert protein_list_line(protein) == "STxB 1 0.5 0 0 -1.1"


def _state(**overrides: object) -> WizardState:
    state = WizardState()
    for name, value in overrides.items():
        setattr(state, name, value)
    return state


def test_outer_leaflet_height_is_half_the_analytical_thickness() -> None:
    state = _state(path_choice="analytical_shape", shape_type="Flat", shape_params={"Thickness": 4.0})
    assert outer_leaflet_height(state) == 2.0


def test_outer_leaflet_height_adds_dl_for_sphere_and_cylinder() -> None:
    for shape in ("Sphere", "Cylinder"):
        params = {"Thickness": 4.0, "DL": 0.5}
        state = _state(path_choice="analytical_shape", shape_type=shape, shape_params=params)
        assert outer_leaflet_height(state) == 2.5


def test_outer_leaflet_height_uses_plm_thickness_on_the_mesh_path() -> None:
    assert outer_leaflet_height(_state(path_choice="mesh_file")) == 1.9
    state = _state(path_choice="mesh_file", plm_overrides={"bilayerThickness": 5.0})
    assert outer_leaflet_height(state) == 2.5


def test_placed_protein_positions_centers_the_structure_then_lifts_it_by_height_plus_z0() -> None:
    positions = np.array([[1.0, 2.0, 5.0], [3.0, 4.0, 7.0]])
    placed = placed_protein_positions(positions, outer_height=2.0, z0=-0.5)
    np.testing.assert_allclose(placed.mean(axis=0), [0.0, 0.0, 1.5])
    np.testing.assert_allclose(placed[1] - placed[0], positions[1] - positions[0])


def test_z0_of_minus_the_outer_height_centers_the_protein_in_the_bilayer() -> None:
    positions = np.array([[0.0, 0.0, 3.0], [0.0, 0.0, 9.0]])
    placed = placed_protein_positions(positions, outer_height=1.9, z0=-1.9)
    assert placed[:, 2].mean() == 0.0


class _FakeInclusions:
    def __init__(self, type_ids: list[int]) -> None:
        self._type_ids = type_ids

    def get_by_type(self, type_id: int) -> list[dict]:
        return [{"type_id": t} for t in self._type_ids if t == type_id]


class _FakeMembrane:
    def __init__(self, type_ids: list[int]) -> None:
        self.inclusions = _FakeInclusions(type_ids)


def test_check_protein_count_passes_when_every_protein_was_placed() -> None:
    protein = _protein(type_id=2, num_proteins=3, radius=6.5)
    check_protein_count(Path("point"), protein, load=lambda _path: _FakeMembrane([1, 2, 2, 2]))


def test_check_protein_count_reports_how_many_fit() -> None:
    protein = _protein(type_id=2, num_proteins=5, radius=6.5)
    with pytest.raises(RuntimeError, match="Only 2 of 5 STxB proteins \\(type 2\\) fit with 6.5 nm"):
        check_protein_count(Path("point"), protein, load=lambda _path: _FakeMembrane([1, 2, 2]))
