"""Detecting a lipid's own membrane-interface anchor bead, from its bond graph alone.

TS2CG's own `libmaker` needs one reference bead per molecule (`-b/--base`)
to anchor its x/y/z offsets to - PO4 (libmaker's own hardcoded default) is
right for ordinary phospholipids, but is simply absent from most other
lipid categories (sterols use ROH, ceramides their own amide/hydroxyl
beads, ...), which libmaker silently skips rather than erroring - this is
exactly why `build_lib_file`'s own `failed_lipids` exists (confirmed
against the real lipidome: cholesterol fails to convert with the default
base). Hardcoding one override name per category would only move the
same problem to an ever-growing lookup table; this detects a reasonable
anchor for ANY lipid directly from its own structure instead.

CALM's own `core/headgroup.py` solves the analogous problem for a real
membrane snapshot: build the bonded graph, contract rings into single
nodes, split into terminal arms around the resulting hub(s), and drop
whichever arms sit farther from the fitted membrane surface than the
remaining interior - the kept atoms are the headgroup. A standalone
topology file (what `libmaker` works from) has no membrane and no fitted
surface to measure distance against, so the SAME structural technique is
reimplemented here independently (no import from CALM - this project
never depends on CALM being installed), with Martini bead-type polarity
standing in for "distance to the interface": a lipid's tails are long,
unbranched runs of apolar ("C"-class) beads, identified by majority
polarity vote per arm instead of 3D distance. Whatever is left after
dropping every tail arm is the molecule's own interfacial region; its
single most polar/charged bead there (Martini's own Q > P > N > C
ranking) is the chosen anchor - matching PO4's own role (a charged
Q-type bead) and ROH's (a polar P-type bead) without hardcoding either
name.

Not every lipid has one scientifically distinguished reference point (a
triglyceride's three glycerol-ester beads are chemically equivalent) -
ties are broken by bond-graph degree (the most structurally central
bead), an honest "a good, consistent choice" rather than a claim of
chemical significance that isn't really there. Any single
consistently-present bead works geometrically as an offset origin
either way.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import networkx as nx

if TYPE_CHECKING:
    from TS2CG.core.itp_parser import AtomRow, MoleculeType

# Martini's own bead-type polarity ranking - the letter right after an
# optional size prefix ("S" small, "T" tiny) names the class: Q (charged)
# > P (polar) > N (intermediate/nonpolar) > C (apolar). An unrecognized
# letter is treated as apolar (rank 0) - the conservative choice, since an
# unusual type is more likely a tail-region bead in practice than a
# genuine interfacial one.
_POLARITY_RANK = {"Q": 3, "P": 2, "N": 1, "C": 0}


def _polarity_class(atype: str) -> str:
    """The Martini polarity letter in `atype`, after stripping an optional size prefix.

    E.g. 'SP1' -> 'P', 'TN6' -> 'N', 'SC4h' -> 'C', 'Q1' -> 'Q', 'C1' -> 'C'.
    """
    t = atype
    if t[:1] in ("S", "T") and len(t) > 1 and t[1:2].isalpha():
        t = t[1:]
    return t[:1].upper()


def _polarity_rank(atype: str) -> int:
    return _POLARITY_RANK.get(_polarity_class(atype), 0)


def is_apolar(atype: str) -> bool:
    return _polarity_class(atype) == "C"


def is_mostly_apolar(nrs: Iterable[int], atoms_by_nr: dict[int, AtomRow]) -> bool:
    """Whether a majority of the atoms `nrs` are apolar beads."""
    nrs = list(nrs)
    apolar_count = sum(1 for nr in nrs if is_apolar(atoms_by_nr[nr].atype))
    return apolar_count * 2 > len(nrs)


def _virtual_site_edges(section: str, row: Any) -> list[tuple[int, int]]:
    """(site, constructing atom) pairs of one virtual-site row. TS2CG's parser turns
    `[ virtual_sitesn ]` rows into `VirtualSiteRow`s and keeps `[ virtual_sites2/3/4 ]`
    rows as token lists, `site ai aj [ak [al]] funct ...`."""
    if not isinstance(row, list):
        return [(row.vid, row.a1), (row.vid, row.a2), (row.vid, row.a3)]
    constructing_count = int(section.removeprefix("virtual_sites"))
    site = int(row[0])
    return [(site, int(token)) for token in row[1 : 1 + constructing_count]]


def bond_graph(mol: MoleculeType) -> nx.Graph:
    """`mol`'s atoms as nodes; its bonds, constraints, and virtual sites joined to their
    constructing atoms as edges."""
    graph = nx.Graph()
    graph.add_nodes_from(a.nr for a in mol.atoms)
    for bond in mol.bonds:
        graph.add_edge(bond.ai, bond.aj)
    for constraint in mol.constraints:
        graph.add_edge(constraint.ai, constraint.aj)
    for section, rows in mol.sections.items():
        if section.startswith("virtual_sites"):
            for row in rows:
                graph.add_edges_from(_virtual_site_edges(section, row))
    return graph


def contract_rings(graph: nx.Graph) -> tuple[nx.Graph, dict[int, set[int]]]:
    """(tree, node_atoms): `graph` with every real cycle contracted to one node.

    Same technique as CALM's own `core/headgroup.py::_contract_rings` - a
    biconnected component of exactly 2 nodes is a single bond and is left
    alone; one of 3+ nodes is an actual ring and is merged into its
    lowest-numbered member.
    """
    node_group = {n: n for n in graph.nodes}
    for component in nx.biconnected_components(graph):
        if len(component) >= 3:
            rep = min(component)
            for n in component:
                node_group[n] = rep

    node_atoms: dict[int, set[int]] = {}
    for original, rep in node_group.items():
        node_atoms.setdefault(rep, set()).add(original)

    tree = nx.Graph()
    tree.add_nodes_from(node_atoms.keys())
    for u, v in graph.edges:
        gu, gv = node_group[u], node_group[v]
        if gu != gv:
            tree.add_edge(gu, gv)

    return tree, node_atoms


def _is_hub(tree: nx.Graph, node_atoms: dict[int, set[int]], n: int) -> bool:
    return tree.degree(n) >= 3 or (len(node_atoms[n]) > 1 and tree.degree(n) >= 2)


def terminal_arms(tree: nx.Graph, node_atoms: dict[int, set[int]]) -> tuple[list[list[int]], list[int]]:
    """(arms, interior) - same traversal as CALM's own `_terminal_arms`."""
    hub_nodes = {n for n in tree.nodes if _is_hub(tree, node_atoms, n)}
    if not hub_nodes:
        leaves = [n for n, d in tree.degree() if d <= 1]
        full_path = nx.shortest_path(tree, leaves[0], leaves[1]) if len(leaves) == 2 else list(tree.nodes)
        mid = len(full_path) // 2
        return [full_path[:mid], full_path[mid:]], []

    arms = []
    visited: set[int] = set()
    for leaf in [n for n, d in tree.degree() if d == 1 and n not in hub_nodes]:
        path = [leaf]
        prev, cur = None, leaf
        while True:
            neighbors = [x for x in tree.neighbors(cur) if x != prev]
            if not neighbors:
                break
            nxt = neighbors[0]
            if nxt in hub_nodes:
                break
            path.append(nxt)
            prev, cur = cur, nxt
        arms.append(path)
        visited.update(path)
    interior = [n for n in tree.nodes if n not in visited]
    return arms, interior


def detect_anchor_bead(mol: MoleculeType) -> str:
    """The atom name to pass as `libmaker`'s own `-b/--base` for `mol`.

    Falls back to `mol.atoms[0].atom` (the first atom in file order) for a
    one-atom molecule, or one with no bonds at all - nothing structural to
    classify, so the molecule's own first bead is as good a choice as any.
    """
    atoms_by_nr = {a.nr: a for a in mol.atoms}
    if len(mol.atoms) <= 1 or not mol.bonds:
        return mol.atoms[0].atom

    graph = bond_graph(mol)
    tree, node_atoms = contract_rings(graph)
    if tree.number_of_nodes() == 1:
        kept_nrs = next(iter(node_atoms.values()))
    else:
        arms, interior = terminal_arms(tree, node_atoms)
        kept_tree_nodes = set(interior)
        for arm in arms:
            arm_nrs = [nr for n in arm for nr in node_atoms[n]]
            if not is_mostly_apolar(arm_nrs, atoms_by_nr):
                kept_tree_nodes |= set(arm)
        if not kept_tree_nodes:  # every arm was a tail and there was no interior at all
            kept_tree_nodes = set(tree.nodes)
        kept_nrs = {nr for n in kept_tree_nodes for nr in node_atoms[n]}

    # Highest Martini polarity wins; ties broken by bond-graph degree (the
    # most structurally central bead) - see module docstring on why a tie
    # here (e.g. a triglyceride's own equivalent glycerol-ester beads) is
    # genuinely not scientifically distinguishable, and an arbitrary but
    # consistent pick is the honest answer.
    best_nr = max(
        kept_nrs,
        key=lambda nr: (_polarity_rank(atoms_by_nr[nr].atype), graph.degree(nr)),
    )
    return atoms_by_nr[best_nr].atom
