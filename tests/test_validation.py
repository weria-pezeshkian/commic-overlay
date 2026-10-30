"""Tests for calm_bridge/validation.py against a tiny synthetic MDAnalysis structure."""

from __future__ import annotations

from pathlib import Path

import MDAnalysis as mda
import numpy as np
import pytest

from commic_overlay.calm.calm_bridge.validation import (
    classify_resnames,
    has_bond_information,
    list_resnames,
    validate_selection,
)


@pytest.fixture
def structure(tmp_path: Path) -> str:
    u = mda.Universe.empty(n_atoms=6, n_residues=3, atom_resindex=[0, 0, 1, 1, 2, 2], trajectory=True)
    u.add_TopologyAttr("name", ["PO4", "GL1", "PO4", "GL1", "NC3", "GL1"])
    u.add_TopologyAttr("resname", ["POPC", "POPC", "CHOL"])
    u.add_TopologyAttr("resid", [1, 2, 3])
    u.atoms.positions = np.array(
        [[0, 0, 0], [1, 0, 0], [10, 0, 0], [11, 0, 0], [20, 0, 0], [21, 0, 0]], dtype=float
    )
    path = tmp_path / "structure.gro"
    u.atoms.write(str(path))
    return str(path)


@pytest.fixture
def bonded_structure(tmp_path: Path) -> str:
    """Two single-resname fragments (POPC, CHOL, like real lipid molecules) plus one
    multi-resname fragment (ALA bonded to GLY, like two residues of one protein chain).

    Written as .pdb (not .gro, which never carries bonds at all) with
    explicit bonds, so they round-trip through CONECT records on reload -
    classify_resnames always opens a fresh Universe from the file path,
    never reuses the in-memory one that built it.
    """
    # residue 0 (POPC, atoms 0-1, bonded) -> its own single-resname fragment
    # residue 1 (CHOL, atoms 2-3, bonded) -> its own single-resname fragment
    # residues 2-3 (ALA, GLY, atoms 4-5, bonded to EACH OTHER) -> one
    # fragment spanning two different resnames, like two residues of a chain
    u = mda.Universe.empty(n_atoms=6, n_residues=4, atom_resindex=[0, 0, 1, 1, 2, 3], trajectory=True)
    u.add_TopologyAttr("name", ["PO4", "GL1", "PO4", "GL1", "CA", "CA"])
    u.add_TopologyAttr("resname", ["POPC", "CHOL", "ALA", "GLY"])
    u.add_TopologyAttr("resid", [1, 2, 3, 4])
    u.atoms.positions = np.array(
        [[0, 0, 0], [1, 0, 0], [10, 0, 0], [11, 0, 0], [20, 0, 0], [21, 0, 0]], dtype=float
    )
    u.add_bonds([(0, 1), (2, 3), (4, 5)])
    path = tmp_path / "bonded.pdb"
    u.atoms.write(str(path))
    return str(path)


def test_validate_selection_matches_existing_atoms(structure: str) -> None:
    result = validate_selection(structure, "name PO4")
    assert result.ok is True
    assert result.n_atoms == 2


def test_validate_selection_empty_match_is_rejected(structure: str) -> None:
    result = validate_selection(structure, "name DOES_NOT_EXIST")
    assert result.ok is False
    assert "no atoms" in result.message


def test_validate_selection_syntax_error_is_caught_not_raised(structure: str) -> None:
    # CALM's own idiom (len(select_atoms(...)) == 0) never catches this -
    # validate_selection must, since the overlay needs a message, not a
    # raised exception reaching the GUI.
    result = validate_selection(structure, "resname (")
    assert result.ok is False
    assert result.message  # some explanatory message, not just a blank reject


def test_validate_selection_missing_structure_file_is_caught(tmp_path: Path) -> None:
    result = validate_selection(str(tmp_path / "does_not_exist.gro"), "name PO4")
    assert result.ok is False
    assert "Could not read structure file" in result.message


def test_list_resnames_returns_unique_sorted_names(structure: str) -> None:
    assert list_resnames(structure) == ["CHOL", "POPC"]


def test_classify_resnames_separates_single_resname_fragments_from_multi(bonded_structure: str) -> None:
    simple, complex_ = classify_resnames(bonded_structure)
    assert simple == ["CHOL", "POPC"]
    assert complex_ == ["ALA", "GLY"]


def test_classify_resnames_falls_back_to_everything_simple_without_bonds(structure: str) -> None:
    # `structure` is .gro (no bonds at all) - fragments can't be computed,
    # so nothing is held back as "complex".
    simple, complex_ = classify_resnames(structure)
    assert simple == ["CHOL", "POPC"]
    assert complex_ == []


def test_has_bond_information_false_for_a_structure_with_no_bonds(structure: str) -> None:
    assert has_bond_information(structure) is False


def test_has_bond_information_true_for_a_structure_with_bonds(bonded_structure: str) -> None:
    assert has_bond_information(bonded_structure) is True


def test_has_bond_information_false_for_a_missing_file(tmp_path: Path) -> None:
    assert has_bond_information(str(tmp_path / "does_not_exist.gro")) is False
