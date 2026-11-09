"""A protein's `.gro` structure: reading it the way PCG does, rotating it, and writing the
rotated copy PCG builds the membrane with.

PCG names each `include`d structure by its title line with the spaces removed
(`GroFile::ReadGroFile`) and writes that name into `.top`; the rotated copy keeps the title,
so the protein keeps its name. The structure turns about its center of geometry: first, with
`align_principal_axis`, so its first principal component points along +z; then by
`rotation_x` about x, then by `rotation_y` about y (degrees).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ..state import ProteinSpec

_COORDINATE_START = 20  # columns before x: residue number and name, atom name and number
_DECIMALS_BELOW_WIDTH = 5  # a .gro coordinate of width w carries w - 5 decimals


@dataclass
class GroStructure:
    title: str
    atom_prefixes: list[str]  # each atom line's first 20 columns
    positions: np.ndarray  # nm, one row per atom
    field_width: int  # width of one coordinate field
    box_line: str


def molecule_name(title: str) -> str:
    """The name PCG gives a structure with this title line, and writes into `.top`."""
    return title.strip().replace(" ", "")


def _coordinate_width(atom_line: str) -> int:
    """The coordinate field width, as the distance between the first two decimal points."""
    first = atom_line.index(".", _COORDINATE_START)
    return atom_line.index(".", first + 1) - first


def read_gro(path: Path) -> GroStructure:
    lines = Path(path).read_text().splitlines()
    count = int(lines[1])
    atom_lines = lines[2 : 2 + count]
    width = _coordinate_width(atom_lines[0])
    positions = np.array(
        [
            [float(line[_COORDINATE_START + i * width : _COORDINATE_START + (i + 1) * width]) for i in range(3)]
            for line in atom_lines
        ]
    )
    return GroStructure(
        title=lines[0],
        atom_prefixes=[line[:_COORDINATE_START] for line in atom_lines],
        positions=positions,
        field_width=width,
        box_line=lines[2 + count] if len(lines) > 2 + count else "",
    )


def format_gro(structure: GroStructure, positions: np.ndarray) -> str:
    """`structure` with `positions` in place of its own, in its own coordinate width."""
    width = structure.field_width
    decimals = width - _DECIMALS_BELOW_WIDTH
    lines = [structure.title, f"{len(positions):5d}"]
    for prefix, (x, y, z) in zip(structure.atom_prefixes, positions, strict=True):
        lines.append(f"{prefix}{x:{width}.{decimals}f}{y:{width}.{decimals}f}{z:{width}.{decimals}f}")
    lines.append(structure.box_line)
    return "\n".join(lines) + "\n"


def rotation_matrix(angle_x: float, angle_y: float) -> np.ndarray:
    """Rotation by `angle_x` degrees about x, followed by `angle_y` degrees about y."""
    a, b = math.radians(angle_x), math.radians(angle_y)
    about_x = np.array([[1.0, 0.0, 0.0], [0.0, math.cos(a), -math.sin(a)], [0.0, math.sin(a), math.cos(a)]])
    about_y = np.array([[math.cos(b), 0.0, math.sin(b)], [0.0, 1.0, 0.0], [-math.sin(b), 0.0, math.cos(b)]])
    return about_y @ about_x


def rotate_about_center(
    positions: np.ndarray, angle_x: float, angle_y: float, align_principal_axis: bool = False
) -> np.ndarray:
    """`positions` turned about their unweighted center of geometry: with
    `align_principal_axis`, first onto their principal axis (`principal_axis_angles`), then
    by `rotation_matrix(angle_x, angle_y)`."""
    turn = rotation_matrix(angle_x, angle_y)
    if align_principal_axis:
        turn = turn @ rotation_matrix(*principal_axis_angles(positions))
    center = positions.mean(axis=0)
    return (positions - center) @ turn.T + center


def footprint_diameter(positions: np.ndarray) -> float:
    """Twice the largest in-plane (x, y) distance of a bead from the center of geometry: how
    far apart two copies' centers must be so their footprints cannot overlap."""
    offsets = positions[:, :2] - positions[:, :2].mean(axis=0)
    return 2.0 * float(np.hypot(offsets[:, 0], offsets[:, 1]).max())


def principal_axis_angles(positions: np.ndarray) -> tuple[float, float]:
    """The rotations (degrees, in [0, 360)) that turn the first principal component of
    `positions` onto +z. Of the axis's two directions, the one pointing up (z >= 0) is used,
    which keeps the tilt at 90° or less."""
    covariance = np.cov(positions - positions.mean(axis=0), rowvar=False)
    _eigenvalues, eigenvectors = np.linalg.eigh(covariance)  # ascending eigenvalues
    axis = eigenvectors[:, -1]
    if axis[2] < 0:
        axis = -axis
    # About x: brings the axis into the xz plane; about y: then onto z.
    angle_x = math.degrees(math.atan2(axis[1], axis[2]))
    angle_y = math.degrees(math.atan2(-axis[0], math.hypot(axis[1], axis[2])))
    return angle_x % 360.0, angle_y % 360.0


def is_rotated(protein: ProteinSpec) -> bool:
    return (
        protein.align_principal_axis or protein.rotation_x % 360.0 != 0.0 or protein.rotation_y % 360.0 != 0.0
    )


def rotated_structure_path(build_directory: Path, protein: ProteinSpec) -> Path:
    return build_directory / f"protein_type{protein.type_id}_rotated.gro"


def structure_path(protein: ProteinSpec, build_directory: Path) -> Path:
    """The `.gro` PCG builds `protein` from: the rotated copy in `build_directory` when the
    protein is rotated, its own file otherwise."""
    return rotated_structure_path(build_directory, protein) if is_rotated(protein) else Path(protein.gro_path)


def write_rotated_structure(protein: ProteinSpec, build_directory: Path) -> None:
    """Writes `protein`'s structure, aligned and rotated as it says, to `rotated_structure_path`."""
    structure = read_gro(Path(protein.gro_path))
    positions = rotate_about_center(
        structure.positions, protein.rotation_x, protein.rotation_y, protein.align_principal_axis
    )
    rotated_structure_path(build_directory, protein).write_text(format_gro(structure, positions))
