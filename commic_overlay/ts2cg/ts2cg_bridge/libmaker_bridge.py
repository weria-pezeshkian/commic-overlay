"""Assembling one TS2CG `.LIB` file scoped to exactly the lipids a run actually needs.

TS2CG's own `libmaker` converts one itp file into one `.LIB` snippet PER
MOLECULE it contains (`TS2CG/tools/libmaker.py::maker_itp`), using a
single shared `-b/--base` reference bead for every molecule in that file
- there is no bulk "build a whole .LIB from many lipids" command, and no
per-molecule base-bead option either. This module runs `libmaker` once
per NEEDED lipid, each in its own isolated single-molecule itp file with
its own `anchor_bead.detect_anchor_bead`-chosen `-b` - never speculatively
on a molecule nothing selected needs, and never assuming every molecule
in a shared source file wants the same reference bead (most do, in this
lipidome's own category-per-file organization, but nothing guarantees
it, and isolating per molecule costs nothing - each conversion is fast).
Keeps only the snippets for lipids actually selected, discards the rest,
and concatenates the kept ones into one `.LIB` file.
"""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .anchor_bead import detect_anchor_bead

LIB_HEADER = "Description Martini Map CG\nVersion Martini 3\n"


def _write_single_molecule_itp(mol, path: Path) -> None:
    """A minimal, valid itp holding just `mol`'s own `[moleculetype]`/`[atoms]`/`[bonds]`/
    `[virtual_sitesn]`/`[constraints]` sections - everything `libmaker`'s own `maker_itp`
    actually reads (`mol.atoms`, `mol.bonds`, `mol.virtual_sites`, and `mol.constraints`
    only if `--consider_constraints` is used, never angles/dihedrals), so isolating one
    molecule per call never needs the rest of its original source file."""
    lines = ["[moleculetype]", f"{mol.name} {mol.nrexcl}", "", "[atoms]"]
    for a in mol.atoms:
        mass = f" {a.mass}" if a.mass is not None else ""
        lines.append(f"{a.nr} {a.atype} {a.resnr} {a.residue} {a.atom} {a.cgnr} {a.charge}{mass}")
    if mol.bonds:
        lines += ["", "[bonds]"]
        for b in mol.bonds:
            lines.append(f"{b.ai} {b.aj} {b.funct} {' '.join(b.params)}")
    if mol.virtual_sites:
        lines += ["", "[virtual_sitesn]"]
        for v in mol.virtual_sites:
            lines.append(f"{v.vid} {v.funct} {v.a1} {v.a2} {v.a3}")
    if mol.constraints:
        lines += ["", "[constraints]"]
        for c in mol.constraints:
            lines.append(f"{c.ai} {c.aj} {c.funct}")
    path.write_text("\n".join(lines) + "\n")


def _run_libmaker(itp_path: Path, base: str, out_dir: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["TS2CG", "libmaker", "-p", str(itp_path), "-b", base, "-o", "lib.txt"],
        cwd=out_dir, check=False, capture_output=True, text=True,
    )


@dataclass(frozen=True)
class LibBuildResult:
    lib_path: Path
    converted_lipids: list[str] = field(default_factory=list)
    failed_lipids: list[str] = field(default_factory=list)


def build_lib_file(
    selected_lipids: list[str],
    lipid_to_itp: dict[str, Path],
    out_path: Path,
    run_libmaker: Callable[[Path, str, Path], subprocess.CompletedProcess] = _run_libmaker,
) -> LibBuildResult:
    """Builds `out_path` as a `.LIB` file containing exactly `selected_lipids`' own sections.

    `lipid_to_itp` maps every selectable lipid name to its own source itp
    file - typically `LipidomeIndex.lipid_to_itp` (`lipidome.py`) merged
    with whatever custom itp files were added via the Select Lipids
    page's own Advanced popup. A name with no entry in `lipid_to_itp`
    (shouldn't happen from the wizard's own UI, but checked rather than
    assumed), or one whose molecule can't be found again inside its own
    source file, comes back in `failed_lipids` without ever calling
    `libmaker`.

    `run_libmaker` is injectable so tests can stub out the real
    subprocess call entirely (see `tests/test_libmaker_bridge.py`).
    """
    from TS2CG.core.itp_parser import read_itp_molecules  # deferred: see introspect.py's own note

    molecules_by_itp: dict[Path, dict[str, object]] = {}
    converted: list[str] = []
    failed: list[str] = []
    snippets: dict[str, str] = {}

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for name in selected_lipids:
            itp_path = lipid_to_itp.get(name)
            if itp_path is None:
                failed.append(name)
                continue

            if itp_path not in molecules_by_itp:
                molecules_by_itp[itp_path] = {mol.name: mol for mol in read_itp_molecules(itp_path)}
            mol = molecules_by_itp[itp_path].get(name)
            if mol is None:
                failed.append(name)
                continue

            isolated_itp = tmp_path / f"{name}.itp"
            _write_single_molecule_itp(mol, isolated_itp)
            base = detect_anchor_bead(mol)
            run_libmaker(isolated_itp, base, tmp_path)

            snippet_path = tmp_path / f"{name}_lib.txt"
            if snippet_path.exists():
                snippets[name] = snippet_path.read_text()
                converted.append(name)
            else:
                failed.append(name)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(LIB_HEADER)
        for name in selected_lipids:
            if name in snippets:
                f.write("\n")
                f.write(snippets[name])

    return LibBuildResult(lib_path=out_path, converted_lipids=converted, failed_lipids=failed)
