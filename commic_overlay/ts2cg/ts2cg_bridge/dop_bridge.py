"""Running `DOP` for the Distribute Domains page.

DOP's `--lipid-specs` file (its CLI default name is `domain_input.txt`) holds one line per
`DopSpec`, `domain_id name percentage curvature density`, with percentages across the
whole file summing to about 1.0. DOP's domain assignment reads only the domain id,
percentage and curvature; name and density go into DOP's placeholder `input.str`, so each
line gets `domain<id>` and 1.

DOP's CLI also writes a placeholder `input.str` to `--new-input`. This overlay's own
`input_str.py::build_input_str()` writes the `input.str` PCG reads, so that placeholder
goes to an `.unused` file in the build directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .python_tools import python_tool_argv

if TYPE_CHECKING:
    from ..state import DopSpec, WizardState

DOMAIN_INPUT_FILENAME = "domain_input.txt"
_UNUSED_DOP_INPUT_STR_FILENAME = "input_DOP.str.unused"


def write_domain_input_file(specs: list[DopSpec], path: Path) -> None:
    """Writes `path` in DOP's own `--lipid-specs` format - one line per spec."""
    lines = [f"{s.domain_id} domain{s.domain_id} {s.percentage:g} {s.curvature:g} 1" for s in specs]
    path.write_text("\n".join(lines) + "\n")


def build_dop_argv(point_dir: str, lipid_specs_path: str, build_dir: str, state: WizardState) -> list[str]:
    """`DOP` argv for the Distribute Domains page's recorded settings, editing `point_dir`
    in place with `--no-backup`."""
    argv = python_tool_argv(
        "DOP",
        "--point-dir", point_dir,
        "--lipid-specs", lipid_specs_path,
        "--leaflet", state.dop_leaflet,
        "--k-factor", str(state.dop_k_factor),
        "--new-input", str(Path(build_dir) / _UNUSED_DOP_INPUT_STR_FILENAME),
        "--no-backup",
    )
    if state.dop_area_weighted:
        argv.append("--area")
    if state.dop_seed is not None:
        argv.extend(["--seed", str(state.dop_seed)])
    return argv
