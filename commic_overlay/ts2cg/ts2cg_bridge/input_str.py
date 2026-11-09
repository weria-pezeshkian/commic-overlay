"""Building `input.str`, TS2CG's own input file for PCG.

Every section's exact field order and the `[Protein List]` terminator are
verified directly against the installed C++ reader
(`cpp/MembraneBuilder/BackMap.cpp`, `{FlatPointMaker,Sphere,Cylinder,
SHGeneric1DPBCPointMaker}.cpp`), not just TS2CG-v2.0/README.md's own
worked example - which is itself subtly wrong: its `[Protein List]`
example ends with `end Protein`, but the real parser
(`BackMap.cpp::FindProteinList`) only ever recognizes a bare `End`/`END`
as the terminator and otherwise hard-errors
(`"protein information in the str file is incomplete"`) - confirmed by
running both forms against the real installed `TS2CG PCG` binary.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from .outputs import build_dir
from .point_placement import protein_list_line
from .protein_structure import structure_path

if TYPE_CHECKING:
    from ..state import WizardState

# Each ShapeType's own [Shape Data] fields, in the order written - verified field-by-field
# against each point-maker's own C++ parser (see analytical_shape_page.py's own module
# docstring for the full story on why these differ subtly between shapes, e.g. Flat's
# Density line carrying 2 values with no separate WallDensity keyword at all).
_SHAPE_FIELD_ORDER = {
    "Flat": ["Box", "WallRange", "Density", "Thickness"],
    "Sphere": ["Box", "Density", "WallDensity", "Thickness", "DL", "Radius"],
    "Cylinder": ["Box", "Density", "WallDensity", "Thickness", "DL", "Radius"],
    "1D_PBC_Fourier": ["Box", "WallRange", "Density", "WallDensity", "Thickness"],
}


def _format_number(value: object) -> str:
    return f"{value:g}" if isinstance(value, float) else str(value)


def _format_value(value: object) -> str:
    if isinstance(value, (tuple, list)):
        return " ".join(_format_number(v) for v in value)
    return _format_number(value)


def _build_lipids_list_section(state: WizardState) -> str:
    lines = ["[Lipids List]"]
    for domain_index in range(state.domain_count):
        lines.append(f"Domain {domain_index}")
        for lipid in state.domain_lipids.get(domain_index, []):
            lines.append(f"{lipid.name} {lipid.ratio_up:g} {lipid.ratio_down:g} {lipid.area_per_lipid:g}")
        lines.append("End")
    return "\n".join(lines)


def _build_shape_data_section(state: WizardState) -> str:
    lines = ["[Shape Data]", f"ShapeType {state.shape_type}"]
    for field_name in _SHAPE_FIELD_ORDER[state.shape_type]:
        if field_name in state.shape_params:
            lines.append(f"{field_name} {_format_value(state.shape_params[field_name])}")
    if state.shape_type == "1D_PBC_Fourier":
        for mode in state.shape_params.get("Modes", []):
            lines.append(f"Mode {_format_value(mode)}")
    lines.append("End")
    return "\n".join(lines)


def _build_protein_list_section(state: WizardState) -> str:
    lines = ["[Protein List]"]
    for protein in state.proteins:
        lines.append(protein_list_line(protein))
    lines.append("End")
    return "\n".join(lines)


def build_shape_only_str(state: WizardState) -> str:
    """Just the `[Shape Data]` section - used for the analytical-shape path's FIRST PCG
    pass (`-function analytical_shape -WPointDir`, building only the point directory,
    before any lipid/protein placement exists yet to write into a full input.str)."""
    return _build_shape_data_section(state) + "\n"


def build_input_str(state: WizardState) -> str:
    """The full `input.str` content for the current wizard state.

    `include` lines use each protein's own absolute `.gro` path, or for a
    rotated protein the rotated copy the pipeline writes into the build
    directory (`protein_structure.py::structure_path`) - a plain
    `std::ifstream` open handles an absolute path the same as a relative one.
    `[Shape Data]` is only written for the analytical-shape path;
    `[Protein List]` only if at least one protein was added - PCG's own
    `CheckProteinInfo` requires one entry per inclusion type id present in
    the point directory, so this must always match whatever
    `point_placement.py` actually placed there.
    """
    build_directory = build_dir(Path(state.working_directory))
    sections = [f"include {structure_path(p, build_directory)}" for p in state.proteins]
    sections.append(_build_lipids_list_section(state))
    if state.path_choice == "analytical_shape":
        sections.append(_build_shape_data_section(state))
    if state.proteins:
        sections.append(_build_protein_list_section(state))
    return "\n".join(sections) + "\n"
