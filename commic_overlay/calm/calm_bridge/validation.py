"""Direct, in-process MDAnalysis calls for fast, read-only checks - never a subprocess.

Unlike running an actual CALM analysis (always a subprocess - see
`runner.py`'s own docstring for why), these are cheap, read-only structure
inspections the overlay can do itself. There's no CALM helper for either
of these, so this follows CALM's own established idiom
(`CALM/core/headgroup.py`'s `len(select_atoms(...)) == 0` check, and its
own error message's suggested `sorted(set(universe.residues.resnames))`)
rather than inventing a different one.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SelectionCheck:
    ok: bool
    message: str
    n_atoms: int = 0


def validate_selection(structure_path: str, selection: str) -> SelectionCheck:
    """Checks `selection` is syntactically valid and matches at least one atom in `structure_path`.

    CALM's own validation idiom only ever checks emptiness - a
    syntactically invalid selection string raises MDAnalysis's own
    `SelectionError` uncaught wherever CALM uses it. This adds the
    missing catch, since the overlay needs a clean, displayable message
    either way, not a raised exception reaching the GUI.
    """
    import MDAnalysis as mda

    try:
        universe = mda.Universe(structure_path)
    except Exception as exc:
        return SelectionCheck(ok=False, message=f"Could not read structure file: {exc}")

    try:
        atoms = universe.select_atoms(selection)
    except Exception as exc:
        return SelectionCheck(ok=False, message=f"Not a valid selection: {exc}")

    if len(atoms) == 0:
        return SelectionCheck(ok=False, message="This selection matches no atoms in the structure.")

    return SelectionCheck(ok=True, message=f"Matches {len(atoms)} atom(s).", n_atoms=len(atoms))


def has_bond_information(structure_path: str) -> bool:
    """True if `structure_path` carries at least one real bond.

    `CALM analyze lipids` needs bonds for its own automatic bond-graph
    headgroup detection (`core/headgroup.py`'s `_require_bonds`) - this is
    the same requirement surfaced early, before the overlay launches a
    real run with a structure that would fail it. In practice only a
    `.tpr` reliably carries bonds: `.gro` never does, and a `.pdb` only
    does if it was written with explicit CONECT records, which most
    `.pdb` files encountered in practice don't have.
    """
    import MDAnalysis as mda

    try:
        universe = mda.Universe(structure_path)
        return len(universe.bonds) > 0
    except Exception:
        return False


def list_resnames(structure_path: str) -> list[str]:
    """Unique residue names in `structure_path`, sorted.

    CALM's own suggested idiom for this (quoted in its own error message
    in `core/headgroup.py`) - no CALM helper does it directly.
    """
    import MDAnalysis as mda

    universe = mda.Universe(structure_path)
    return sorted(set(universe.residues.resnames))


def classify_resnames(structure_path: str) -> tuple[list[str], list[str]]:
    """(simple, complex) resnames in `structure_path`, each sorted.

    Grouped by MDAnalysis "fragment" - a connected component of the bond
    graph, i.e. one whole molecule. A real lipid (or water, or an ion) is
    normally its own fragment containing exactly one resname; a protein
    chain is one single fragment containing many different amino-acid
    resnames bonded together. "simple" is every resname that only ever
    appears in a one-resname fragment - the real lipid-species
    candidates; "complex" is every resname that appears in at least one
    multi-resname fragment (a resname appearing both ways, unusual, is
    still classified "complex" - safer to under-offer it as a lipid
    candidate than over-offer it).

    Falls back to `(list_resnames(structure_path), [])` - everything
    "simple" - when the structure carries no bond information at all
    (fragments can't be computed without bonds): there is nothing to tell
    a lipid from a protein residue apart with in that case, so this never
    hides a resname the caller couldn't otherwise find.
    """
    import MDAnalysis as mda

    universe = mda.Universe(structure_path)
    try:
        fragments = universe.atoms.fragments
    except mda.exceptions.NoDataError:
        return list_resnames(structure_path), []

    simple: set[str] = set()
    complex_: set[str] = set()
    for fragment in fragments:
        resnames_in_fragment = set(fragment.residues.resnames)
        if len(resnames_in_fragment) == 1:
            simple.update(resnames_in_fragment)
        else:
            complex_.update(resnames_in_fragment)

    simple -= complex_
    return sorted(simple), sorted(complex_)
