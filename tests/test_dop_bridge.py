"""Tests for ts2cg_bridge/dop_bridge.py."""

from __future__ import annotations

from pathlib import Path

from commic_overlay.ts2cg.state import DopSpec, WizardState
from commic_overlay.ts2cg.ts2cg_bridge.dop_bridge import build_dop_argv, write_domain_input_file


def test_write_domain_input_file_formats_one_line_per_spec(tmp_path: Path) -> None:
    specs = [
        DopSpec(domain_id=0, percentage=0.6, curvature=0.0),
        DopSpec(domain_id=1, percentage=0.4, curvature=0.05),
    ]
    path = tmp_path / "domain_input.txt"
    write_domain_input_file(specs, path)
    lines = path.read_text().splitlines()
    assert lines == ["0 domain0 0.6 0 1", "1 domain1 0.4 0.05 1"]


def test_build_dop_argv_includes_required_fields(tmp_path: Path) -> None:
    state = WizardState()
    state.dop_leaflet = "outer"
    state.dop_k_factor = 2.5
    argv = build_dop_argv("point", "domain_input.txt", str(tmp_path), state)
    assert argv[3] == "DOP"
    assert argv[argv.index("--point-dir") + 1] == "point"
    assert argv[argv.index("--lipid-specs") + 1] == "domain_input.txt"
    assert argv[argv.index("--leaflet") + 1] == "outer"
    assert argv[argv.index("--k-factor") + 1] == "2.5"
    assert "--no-backup" in argv


def test_build_dop_argv_new_input_points_into_build_dir_not_point_dir(tmp_path: Path) -> None:
    state = WizardState()
    argv = build_dop_argv("point", "domain_input.txt", str(tmp_path), state)
    new_input = argv[argv.index("--new-input") + 1]
    assert new_input.startswith(str(tmp_path))


def test_build_dop_argv_omits_area_and_seed_by_default() -> None:
    state = WizardState()
    argv = build_dop_argv("point", "domain_input.txt", "build", state)
    assert "--area" not in argv
    assert "--seed" not in argv


def test_build_dop_argv_includes_area_and_seed_when_set() -> None:
    state = WizardState()
    state.dop_area_weighted = True
    state.dop_seed = 7
    argv = build_dop_argv("point", "domain_input.txt", "build", state)
    assert "--area" in argv
    assert argv[argv.index("--seed") + 1] == "7"
