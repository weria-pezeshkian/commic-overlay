"""Tests for ts2cg_bridge/apl_estimate.py."""

from __future__ import annotations

import csv
import math
from pathlib import Path

import pytest
from TS2CG.core.itp_parser import AtomRow, BondRow, MoleculeType, read_itp_molecules

from commic_overlay.ts2cg.ts2cg_bridge.apl_estimate import (
    BENCHMARK_RELATIVE_PATH,
    FALLBACK_APL,
    REFERENCE_TEMPERATURE,
    STEROL_APL,
    benchmark_apls,
    estimate_apl,
    model_apl,
    summarize_tails,
)
from commic_overlay.ts2cg.ts2cg_bridge.lipidome import index_lipidome, itp_dir

LIPIDOME = Path.home() / ".cache" / "commic_overlay" / "lipidome" / "M3-Lipid-Parameters"

_POPC_ITP = """[ moleculetype ]
POPC 1

[ atoms ]
 1 Q1   1 POPC NC3 1  1.0
 2 Q5   1 POPC PO4 2 -1.0
 3 SN4a 1 POPC GL1 3  0
 4 SN4a 1 POPC GL2 4  0
 5 C1   1 POPC C1A 5  0
 6 C4h  1 POPC D2A 6  0
 7 C1   1 POPC C3A 7  0
 8 C1   1 POPC C4A 8  0
 9 SC1  1 POPC C1B 9  0
10 C1   1 POPC C2B 10 0
11 C1   1 POPC C3B 11 0
12 C1   1 POPC C4B 12 0

[ bonds ]
 1  2 1
 2  3 1
 2  4 1
 3  4 1
 3  5 1
 5  6 1
 6  7 1
 7  8 1
 4  9 1
 9 10 1
10 11 1
11 12 1
"""


def _atom(nr: int, atype: str, atom: str) -> AtomRow:
    return AtomRow(nr=nr, atype=atype, resnr=1, residue="MOL", atom=atom, cgnr=nr, charge=0.0)


def _mol(atoms: list[tuple[str, str]], bonds: list[tuple[int, int]]) -> MoleculeType:
    mol = MoleculeType(name="MOL", nrexcl=1)
    for nr, (atype, atom) in enumerate(atoms, start=1):
        mol.add_row("atoms", _atom(nr, atype, atom))
    for ai, aj in bonds:
        mol.add_row("bonds", BondRow(ai=ai, aj=aj, funct=1))
    return mol


def _write_lipidome(root: Path, benchmark_rows: list[tuple[str, float, float]]) -> Path:
    itps = root / "ITPs"
    itps.mkdir(parents=True)
    itp_path = itps / "lipids.itp"
    itp_path.write_text(_POPC_ITP)
    if benchmark_rows:
        csv_path = root / BENCHMARK_RELATIVE_PATH
        csv_path.parent.mkdir(parents=True)
        with csv_path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["lipid", "temp_K", "exp_apl_nm^2", "exp_apl_err_nm^2", "sim_apl_nm^2", "sim_apl_err_nm^2"])
            for name, temperature, apl in benchmark_rows:
                writer.writerow([name, temperature, 0.0, 0.0, apl, 0.0])
    return itp_path


def test_popc_has_two_tails_with_one_unsaturated_bead(tmp_path: Path) -> None:
    itp_path = _write_lipidome(tmp_path, [])
    mol = {m.name: m for m in read_itp_molecules(itp_path)}["POPC"]
    summary = summarize_tails(mol)
    assert summary is not None
    assert (summary.tails, summary.tail_beads, summary.unsaturated_beads) == (2, 8, 1)
    assert not summary.ethanolamine and not summary.sterol


def test_ethanolamine_head_lowers_the_model_apl() -> None:
    pc = summarize_tails(_mol([("Q1", "NC3"), ("Q5", "PO4"), ("C1", "C1A"), ("C1", "C2A")], [(1, 2), (2, 3), (3, 4)]))
    pe = summarize_tails(_mol([("Q1", "NH3"), ("Q5", "PO4"), ("C1", "C1A"), ("C1", "C2A")], [(1, 2), (2, 3), (3, 4)]))
    assert pe is not None and pe.ethanolamine
    assert model_apl(pe) == pytest.approx(model_apl(pc) - 0.0512)


def test_a_ring_of_apolar_beads_is_a_sterol() -> None:
    atoms = [("SP1", "ROH"), ("SC4", "R1"), ("SC3", "R2"), ("TC2", "R3"), ("C1", "C1"), ("C1", "C2")]
    mol = _mol(atoms, [(1, 2), (2, 3), (3, 4), (4, 2), (4, 5), (5, 6)])
    assert model_apl(summarize_tails(mol)) == STEROL_APL


def test_virtual_sites_join_a_sterol_ring_system() -> None:
    atoms = [("P1", "ROH"), ("SC4", "R1"), ("SC3", "R2"), ("SC3", "R3"), ("C2", "C1"), ("C2", "C2")]
    mol = _mol(atoms, [(2, 3), (3, 5), (5, 6)])
    mol.add_row("virtual_sites3", ["1", "5", "3", "2", "4", "1.0", "0.3", "0.2"])
    mol.add_row("virtual_sites3", ["4", "5", "3", "2", "4", "-0.4", "0.8", "0.0"])
    summary = summarize_tails(mol)
    assert summary is not None and summary.sterol
    assert model_apl(summary) == STEROL_APL


def test_a_disconnected_molecule_gets_the_fallback() -> None:
    mol = _mol([("P1", "A"), ("P1", "B"), ("P1", "C")], [(1, 2)])
    assert summarize_tails(mol) is None
    assert model_apl(None) == FALLBACK_APL


def test_benchmark_value_is_taken_at_the_closest_temperature_and_shifted(tmp_path: Path) -> None:
    itp_path = _write_lipidome(tmp_path, [("POPC", 293.15, 0.50), ("POPC", 303.15, 0.60), ("POPC", 333.15, 0.70)])
    expected = 0.60 + 0.0013 * (REFERENCE_TEMPERATURE - 303.15)
    assert estimate_apl(itp_path, "POPC") == round(expected, 3)


def test_a_lipid_missing_from_the_benchmark_uses_the_tail_model(tmp_path: Path) -> None:
    itp_path = _write_lipidome(tmp_path, [("DOPC", 303.15, 0.65)])
    expected = 0.3335 * 2 - 0.0117 * 8 + 0.0327 * 1
    assert estimate_apl(itp_path, "POPC") == round(expected, 3)


def test_no_benchmark_file_uses_the_tail_model(tmp_path: Path) -> None:
    itp_path = _write_lipidome(tmp_path, [])
    assert benchmark_apls(tmp_path / BENCHMARK_RELATIVE_PATH) == {}
    assert estimate_apl(itp_path, "POPC") == round(0.3335 * 2 - 0.0117 * 8 + 0.0327, 3)


@pytest.mark.skipif(not (LIPIDOME / BENCHMARK_RELATIVE_PATH).is_file(), reason="Martini 3 lipidome not cached")
def test_model_reproduces_the_lipidome_benchmark() -> None:
    lipid_to_itp = index_lipidome(itp_dir(LIPIDOME)).lipid_to_itp
    errors = []
    with (LIPIDOME / BENCHMARK_RELATIVE_PATH).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            mol = {m.name: m for m in read_itp_molecules(Path(lipid_to_itp[row["lipid"]]))}[row["lipid"]]
            predicted = model_apl(summarize_tails(mol)) + 0.0013 * (float(row["temp_K"]) - REFERENCE_TEMPERATURE)
            errors.append(predicted - float(row["sim_apl_nm^2"]))
    assert len(errors) == 66
    assert math.sqrt(sum(e * e for e in errors) / len(errors)) < 0.025
    assert max(abs(e) for e in errors) < 0.045
