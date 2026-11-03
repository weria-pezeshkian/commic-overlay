"""Default area per lipid (APL, nm²) for a lipid's Sort Lipids row, from its ITP.

A lipid listed in the lipidome's own benchmark (`Martini_lipid_Benchmark/figure1_apl_data.csv`,
beside the `ITPs` directory) gets its simulated Martini 3 APL at the benchmark temperature
closest to `REFERENCE_TEMPERATURE`, shifted to that temperature by `_PER_KELVIN`.

Any other lipid gets a linear model of its tails, found as the majority-apolar arms of its
bond graph (`anchor_bead.py`):

    APL = 0.3335 * tails - 0.0117 * tail beads + 0.0327 * unsaturated tail beads
          - 0.0512 * (ethanolamine head) + 0.0013 * (T - 310 K)

Unsaturated beads are tail beads whose name starts with "D", the lipidome's naming for a
cis double bond; the ethanolamine head is an atom named "NH3". The coefficients are a
least-squares fit to that benchmark's 66 simulated APLs (28 lipids, 293-338 K), which the
model reproduces with an rms error of 0.022 nm² and a largest error of 0.042 nm².

A molecule with a ring system of mostly apolar beads (a sterol) gets `STEROL_APL`, and one with
no tail or a disconnected bond graph gets `FALLBACK_APL`. Virtual sites count as bonded to
the atoms they are built from, which is what joins cholesterol's ring beads.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

import networkx as nx

from .anchor_bead import bond_graph, contract_rings, is_mostly_apolar, terminal_arms

if TYPE_CHECKING:
    from TS2CG.core.itp_parser import MoleculeType

REFERENCE_TEMPERATURE = 310.0
STEROL_APL = 0.40
FALLBACK_APL = 0.60
BENCHMARK_RELATIVE_PATH = Path("Martini_lipid_Benchmark") / "figure1_apl_data.csv"

_PER_TAIL = 0.3335
_PER_TAIL_BEAD = -0.0117
_PER_UNSATURATED_BEAD = 0.0327
_ETHANOLAMINE = -0.0512
_PER_KELVIN = 0.0013


@dataclass(frozen=True)
class TailSummary:
    tails: int
    tail_beads: int
    unsaturated_beads: int
    ethanolamine: bool
    sterol: bool


def summarize_tails(mol: MoleculeType) -> TailSummary | None:
    """`mol`'s tails, or None when its bond graph is a single bead or disconnected."""
    atoms_by_nr = {a.nr: a for a in mol.atoms}
    graph = bond_graph(mol)
    if graph.number_of_nodes() <= 1 or not nx.is_connected(graph):
        return None
    tree, node_atoms = contract_rings(graph)
    sterol = any(len(group) >= 3 and is_mostly_apolar(group, atoms_by_nr) for group in node_atoms.values())
    tails: list[list[int]] = []
    if tree.number_of_nodes() > 1:
        arms, _interior = terminal_arms(tree, node_atoms)
        for arm in arms:
            arm_nrs = [nr for node in arm for nr in node_atoms[node]]
            if is_mostly_apolar(arm_nrs, atoms_by_nr):
                tails.append(arm_nrs)
    return TailSummary(
        tails=len(tails),
        tail_beads=sum(len(tail) for tail in tails),
        unsaturated_beads=sum(1 for tail in tails for nr in tail if atoms_by_nr[nr].atom.startswith("D")),
        ethanolamine=any(a.atom == "NH3" for a in mol.atoms),
        sterol=sterol,
    )


def model_apl(summary: TailSummary | None) -> float:
    """The tail model's APL at `REFERENCE_TEMPERATURE`."""
    if summary is None or (summary.tails == 0 and not summary.sterol):
        return FALLBACK_APL
    if summary.sterol:
        return STEROL_APL
    return (
        _PER_TAIL * summary.tails
        + _PER_TAIL_BEAD * summary.tail_beads
        + _PER_UNSATURATED_BEAD * summary.unsaturated_beads
        + _ETHANOLAMINE * summary.ethanolamine
    )


@cache
def benchmark_apls(csv_path: Path) -> dict[str, float]:
    """Lipid name -> simulated APL at `REFERENCE_TEMPERATURE`, from the benchmark row at the
    temperature closest to it. Empty when `csv_path` does not exist."""
    if not csv_path.is_file():
        return {}
    closest: dict[str, tuple[float, float]] = {}
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            temperature = float(row["temp_K"])
            apl = float(row["sim_apl_nm^2"])
            name = row["lipid"]
            if name not in closest or abs(temperature - REFERENCE_TEMPERATURE) < abs(
                closest[name][0] - REFERENCE_TEMPERATURE
            ):
                closest[name] = (temperature, apl)
    return {
        name: apl + _PER_KELVIN * (REFERENCE_TEMPERATURE - temperature) for name, (temperature, apl) in closest.items()
    }


@cache
def _molecules(itp_path: Path) -> dict[str, MoleculeType]:
    from TS2CG.core.itp_parser import read_itp_molecules

    return {mol.name: mol for mol in read_itp_molecules(itp_path)}


@cache
def estimate_apl(itp_path: Path, name: str) -> float:
    """Default APL for lipid `name` defined in `itp_path`, rounded to 0.001 nm²."""
    benchmark = benchmark_apls(itp_path.parent.parent / BENCHMARK_RELATIVE_PATH)
    if name in benchmark:
        return round(benchmark[name], 3)
    mol = _molecules(itp_path).get(name)
    return round(model_apl(summarize_tails(mol) if mol is not None else None), 3)
