"""Tests for ts2cg_bridge/point_placement.py."""

from __future__ import annotations

from commic_overlay.ts2cg.state import ProteinSpec
from commic_overlay.ts2cg.ts2cg_bridge.point_placement import build_inu_argv, protein_list_line


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
