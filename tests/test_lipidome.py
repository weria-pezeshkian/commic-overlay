"""Tests for ts2cg_bridge/lipidome.py - offline, against a small synthetic itp fixture tree.

`fetch_lipidome()` itself (a real HTTPS download) is deliberately not
covered here - verified manually against the real repo instead, so this
suite stays network-free.
"""

from __future__ import annotations

from pathlib import Path

from commic_overlay.ts2cg.ts2cg_bridge.lipidome import group_label, index_lipidome, is_lipid_itp_filename


def _write_itp(path: Path, molecules: list[str]) -> None:
    lines = []
    for name in molecules:
        lines.append("[ moleculetype ]")
        lines.append(f"{name} 1")
        lines.append("[ atoms ]")
        lines.append("1 Q1 1 " + name + " R1 1 0.0 72.0")
    path.write_text("\n".join(lines) + "\n")


def test_is_lipid_itp_filename_excludes_known_non_lipid_files() -> None:
    assert is_lipid_itp_filename("martini_v3.0.0.itp") is False
    assert is_lipid_itp_filename("martini_v3.0.0_ffbonded_v2.itp") is False
    assert is_lipid_itp_filename("martini_v3.0.0_ions_v1.itp") is False
    assert is_lipid_itp_filename("martini_v3.0.0_solvents_v1.itp") is False


def test_is_lipid_itp_filename_includes_real_lipid_category_files() -> None:
    assert is_lipid_itp_filename("martini_v3.0.0_phospholipids_PC_v2.itp") is True
    assert is_lipid_itp_filename("martini_v3.0.0_sterols_v1.itp") is True
    assert is_lipid_itp_filename("martini_v3.0.0_DOTAP_v2.itp") is True


def test_group_label_strips_prefix_and_version_suffix() -> None:
    assert group_label(Path("martini_v3.0.0_phospholipids_PC_v2.itp")) == "phospholipids PC"
    assert group_label(Path("martini_v3.0.0_sterols_v1.itp")) == "sterols"
    assert group_label(Path("martini_v3.0.0_DOTAP_v2.itp")) == "DOTAP"


def test_index_lipidome_maps_lipids_to_their_source_file(tmp_path: Path) -> None:
    pc = tmp_path / "martini_v3.0.0_phospholipids_PC_v2.itp"
    _write_itp(pc, ["POPC", "DOPC"])
    sterols = tmp_path / "martini_v3.0.0_sterols_v1.itp"
    _write_itp(sterols, ["CHOL"])

    index = index_lipidome(tmp_path)

    assert index.lipid_to_itp["POPC"] == pc
    assert index.lipid_to_itp["DOPC"] == pc
    assert index.lipid_to_itp["CHOL"] == sterols
    assert index.itp_to_lipids[pc] == ["POPC", "DOPC"]


def test_index_lipidome_excludes_non_lipid_itp_files_even_with_real_moleculetypes(tmp_path: Path) -> None:
    ions = tmp_path / "martini_v3.0.0_ions_v1.itp"
    _write_itp(ions, ["NA", "CL"])  # a real [moleculetype] block, deliberately excluded anyway
    sterols = tmp_path / "martini_v3.0.0_sterols_v1.itp"
    _write_itp(sterols, ["CHOL"])

    index = index_lipidome(tmp_path)

    assert "NA" not in index.lipid_to_itp
    assert "CL" not in index.lipid_to_itp
    assert "CHOL" in index.lipid_to_itp


def test_index_lipidome_ignores_itp_files_with_no_moleculetypes(tmp_path: Path) -> None:
    base = tmp_path / "martini_v3.0.0.itp"
    base.write_text("; just bead type definitions, no [ moleculetype ]\n")
    sterols = tmp_path / "martini_v3.0.0_sterols_v1.itp"
    _write_itp(sterols, ["CHOL"])

    index = index_lipidome(tmp_path)

    assert base not in index.itp_to_lipids
    assert sterols in index.itp_to_lipids
