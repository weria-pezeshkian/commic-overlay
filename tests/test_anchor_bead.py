"""Tests for ts2cg_bridge/anchor_bead.py."""

from __future__ import annotations

from TS2CG.core.itp_parser import AtomRow, BondRow, MoleculeType

from commic_overlay.ts2cg.ts2cg_bridge.anchor_bead import detect_anchor_bead


def _atom(nr: int, atype: str, atom: str, charge: float = 0.0) -> AtomRow:
    return AtomRow(nr=nr, atype=atype, resnr=1, residue="MOL", atom=atom, cgnr=nr, charge=charge)


def _mol(name: str, atoms: list[AtomRow], bonds: list[tuple[int, int]]) -> MoleculeType:
    mol = MoleculeType(name=name, nrexcl=1)
    for a in atoms:
        mol.add_row("atoms", a)
    for ai, aj in bonds:
        mol.add_row("bonds", BondRow(ai=ai, aj=aj, funct=1))
    return mol


def test_detects_po4_for_a_simple_phospholipid_like_chain() -> None:
    # NC3(Q1) - PO4(Q5) - GL1(SN4a) - C1A(C1) - C2A(C1): a straight chain, no ring,
    # no hub - splits into two arms at the midpoint; the all-apolar tail arm (C1A,
    # C2A) is dropped, PO4 (highest-ranked Q-class bead in what's left) wins.
    atoms = [
        _atom(1, "Q1", "NC3", charge=1.0),
        _atom(2, "Q5", "PO4", charge=-1.0),
        _atom(3, "SN4a", "GL1"),
        _atom(4, "C1", "C1A"),
        _atom(5, "C1", "C2A"),
    ]
    mol = _mol("POPC", atoms, [(1, 2), (2, 3), (3, 4), (4, 5)])
    assert detect_anchor_bead(mol) == "PO4"


def test_detects_roh_for_a_sterol_like_single_tail() -> None:
    atoms = [_atom(1, "P1", "ROH"), _atom(2, "SC1", "R1"), _atom(3, "C1", "R2")]
    mol = _mol("CHOL", atoms, [(1, 2), (2, 3)])
    assert detect_anchor_bead(mol) == "ROH"


def test_detects_a_charged_headgroup_bead_for_a_cationic_lipid() -> None:
    # NC3(Q1, charged) - GL1(SN4a) branching into two tails - matches DOTAP's own
    # real shape (a single charged headgroup bead, two apolar tails).
    atoms = [
        _atom(1, "Q1", "NC3", charge=1.0),
        _atom(2, "SN4a", "GL1"),
        _atom(3, "SN4a", "GL2"),
        _atom(4, "C1", "C1A"),
        _atom(5, "C1", "C1B"),
    ]
    mol = _mol("DOTAP", atoms, [(1, 2), (2, 3), (2, 4), (3, 5)])
    assert detect_anchor_bead(mol) == "NC3"


def test_falls_back_to_first_atom_for_a_single_bead_molecule() -> None:
    mol = _mol("W", [_atom(1, "P4", "W")], [])
    assert detect_anchor_bead(mol) == "W"


def test_falls_back_to_first_atom_when_there_are_no_bonds_at_all() -> None:
    mol = _mol("XX", [_atom(1, "C1", "A"), _atom(2, "C1", "B")], [])
    assert detect_anchor_bead(mol) == "A"


def test_ring_headgroup_wins_over_two_apolar_tails_like_a_ceramide() -> None:
    # A 3-membered ring (COH-OH1-AM2, all polar/intermediate) with two apolar
    # tails hanging off it - mirrors the real ceramide topology verified against
    # the actual Martini 3 lipidome.
    atoms = [
        _atom(1, "TN6", "COH"),
        _atom(2, "SP1", "OH1"),
        _atom(3, "SP2", "AM2"),
        _atom(4, "SC4h", "T1A"),
        _atom(5, "C1", "C2A"),
        _atom(6, "SC1", "C1B"),
        _atom(7, "C1", "C2B"),
    ]
    mol = _mol("UCER", atoms, [(1, 2), (1, 3), (2, 3), (2, 4), (4, 5), (3, 6), (6, 7)])
    anchor = detect_anchor_bead(mol)
    assert anchor in ("OH1", "AM2")  # the two P-class ring beads outrank COH's N-class


def test_ties_fall_back_to_the_most_structurally_central_bead() -> None:
    # Three chemically-identical SN4a glycerol-ester beads (a triglyceride-like
    # shape) all tie on polarity - the central one (degree 3, connected to all
    # three tails) should win over the two peripheral ones (degree 2 each).
    atoms = [
        _atom(1, "SN4a", "GL1"),
        _atom(2, "SN4a", "GL2"),
        _atom(3, "SN4a", "GL3"),
        _atom(4, "C1", "C1A"),
        _atom(5, "C1", "C1B"),
        _atom(6, "C1", "C1C"),
    ]
    mol = _mol("TRIO", atoms, [(1, 2), (2, 3), (1, 4), (2, 5), (3, 6)])
    assert detect_anchor_bead(mol) == "GL2"
