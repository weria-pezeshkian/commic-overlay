"""Placing protein inclusions onto a TS2CG point directory, and the `input.str`
`[Protein List]` entry each placed protein needs alongside it.

One `INU` call per added protein (`state.py`'s `ProteinSpec`), each with its own
`--protein-type` id. Successive calls edit the same point directory in place, so
`ts2cg_bridge/pipeline.py` runs them one after another.
"""

from __future__ import annotations

from ..state import ProteinSpec
from .python_tools import python_tool_argv


def build_inu_argv(point_dir: str, protein: ProteinSpec) -> list[str]:
    """`INU` argv for one protein's own scatter placement.

    Overwrites `point_dir` in place with `--no-backup`, so a later protein's `INU` call
    builds on the same freshly built directory.
    """
    argv = python_tool_argv(
        "INU",
        "--point-dir", point_dir,
        "--protein-type", str(protein.type_id),
        "--radius", str(protein.radius),
        "--num-proteins", str(protein.num_proteins),
        "--k-factor", str(protein.k_factor),
        "--no-backup",
    )
    if protein.target_curvature is not None:
        argv.extend(["--curvature", str(protein.target_curvature)])
    if protein.seed is not None:
        argv.extend(["--seed", str(protein.seed)])
    return argv


def protein_list_line(protein: ProteinSpec) -> str:
    """One `input.str` `[Protein List]` line for `protein`: `ProteinName ID Ratio Phi Theta Z0`.

    Phi/Theta are always written as `0` - parsed by PCG's own reader
    (`BackMap.cpp`'s `FindProteinList`) but not visibly used anywhere in
    its actual placement transform in this TS2CG version (see the plan's
    own verified-facts note on this), so there's nothing meaningful to set
    them to; `0 0` matches every worked example in TS2CG's own README and
    tutorials.
    """
    return f"{protein.name} {protein.type_id} {protein.ratio} 0 0 {protein.z0}"
