"""Tests for ts2cg_bridge/protein_structure.py."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from commic_overlay.ts2cg.state import ProteinSpec, WizardState
from commic_overlay.ts2cg.ts2cg_bridge.input_str import build_input_str
from commic_overlay.ts2cg.ts2cg_bridge.outputs import build_dir
from commic_overlay.ts2cg.ts2cg_bridge.pipeline import PythonStep, build_pipeline
from commic_overlay.ts2cg.ts2cg_bridge.protein_structure import (
    footprint_diameter,
    format_gro,
    molecule_name,
    principal_axis_angles,
    read_gro,
    rotate_about_center,
    rotated_structure_path,
    rotation_matrix,
    structure_path,
    write_rotated_structure,
)

_GRO = """My protein t= 0.0
    3
    1MET     BB    1   1.000   2.000   3.000  0.1000  0.2000  0.3000
    1MET    SC1    2   1.500   2.000   3.000
    2LEU     BB    3   1.000   2.500   4.000
   5.00000   5.00000   5.00000
"""


def _write_gro(tmp_path: Path) -> Path:
    path = tmp_path / "protein.gro"
    path.write_text(_GRO)
    return path


def _protein(gro_path: Path, **overrides: object) -> ProteinSpec:
    values: dict[str, object] = {"type_id": 2, "name": "Myprotein", "gro_path": str(gro_path)}
    values.update(overrides)
    return ProteinSpec(**values)


def test_read_gro_reads_title_prefixes_positions_and_box(tmp_path: Path) -> None:
    structure = read_gro(_write_gro(tmp_path))
    assert structure.title == "My protein t= 0.0"
    assert structure.atom_prefixes[1] == "    1MET    SC1    2"
    np.testing.assert_allclose(structure.positions[2], [1.0, 2.5, 4.0])
    assert structure.field_width == 8
    assert structure.box_line == "   5.00000   5.00000   5.00000"


def test_read_gro_reads_wider_coordinate_fields(tmp_path: Path) -> None:
    path = tmp_path / "wide.gro"
    path.write_text("wide\n    1\n    1MET     BB    1   1.00000   2.00000-103.50000\n   1 1 1\n")
    structure = read_gro(path)
    assert structure.field_width == 10
    np.testing.assert_allclose(structure.positions[0], [1.0, 2.0, -103.5])


def test_format_gro_round_trips_the_structure_without_velocities(tmp_path: Path) -> None:
    structure = read_gro(_write_gro(tmp_path))
    text = format_gro(structure, structure.positions)
    assert text.splitlines()[2] == "    1MET     BB    1   1.000   2.000   3.000"
    assert text.splitlines()[0] == structure.title
    reread_path = tmp_path / "again.gro"
    reread_path.write_text(text)
    np.testing.assert_allclose(read_gro(reread_path).positions, structure.positions)


def test_molecule_name_removes_spaces_like_pcg() -> None:
    assert molecule_name("  My protein t= 0.0 ") == "Myproteint=0.0"


def test_rotation_matrix_turns_about_x_then_about_y() -> None:
    np.testing.assert_allclose(rotation_matrix(90.0, 0.0) @ [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], atol=1e-12)
    np.testing.assert_allclose(rotation_matrix(0.0, 90.0) @ [0.0, 0.0, 1.0], [1.0, 0.0, 0.0], atol=1e-12)
    np.testing.assert_allclose(rotation_matrix(90.0, 90.0) @ [0.0, 1.0, 0.0], [1.0, 0.0, 0.0], atol=1e-12)
    np.testing.assert_allclose(rotation_matrix(360.0, 360.0), np.eye(3), atol=1e-12)


def test_rotate_about_center_keeps_the_center_and_the_distances() -> None:
    positions = np.array([[1.0, 2.0, 3.0], [4.0, 0.0, 1.0], [2.0, 5.0, -1.0]])
    rotated = rotate_about_center(positions, 37.0, 210.0)
    np.testing.assert_allclose(rotated.mean(axis=0), positions.mean(axis=0))
    np.testing.assert_allclose(
        np.linalg.norm(rotated[0] - rotated[1]), np.linalg.norm(positions[0] - positions[1])
    )


def test_principal_axis_angles_turn_the_long_axis_onto_z() -> None:
    rng = np.random.default_rng(7)
    direction = np.array([0.6, -0.3, 0.2])
    direction /= np.linalg.norm(direction)
    positions = np.outer(rng.uniform(-5.0, 5.0, 400), direction) + rng.normal(0.0, 0.3, (400, 3)) + 3.0
    angle_x, angle_y = principal_axis_angles(positions)
    assert 0.0 <= angle_x < 360.0 and 0.0 <= angle_y < 360.0
    rotated = rotate_about_center(positions, angle_x, angle_y)
    centered = rotated - rotated.mean(axis=0)
    _values, vectors = np.linalg.eigh(np.cov(centered, rowvar=False))
    assert abs(vectors[:, -1] @ [0.0, 0.0, 1.0]) > 0.9999
    assert rotation_matrix(angle_x, angle_y) @ direction @ [0.0, 0.0, 1.0] > 0.99


def test_principal_axis_angles_leave_an_upright_structure_unturned() -> None:
    positions = np.array([[0.0, 0.0, z] for z in range(10)]) + [[0.1, 0.0, 0.0], [0.0, 0.1, 0.0]] * 5
    angle_x, angle_y = principal_axis_angles(positions)
    assert min(angle_x, 360.0 - angle_x) < 1.0
    assert min(angle_y, 360.0 - angle_y) < 1.0


def test_structure_path_uses_the_rotated_copy_only_when_rotated(tmp_path: Path) -> None:
    gro = _write_gro(tmp_path)
    assert structure_path(_protein(gro), tmp_path) == gro
    assert structure_path(_protein(gro, rotation_x=360.0, rotation_y=0.0), tmp_path) == gro
    rotated = _protein(gro, rotation_y=45.0)
    assert structure_path(rotated, tmp_path) == tmp_path / "protein_type2_rotated.gro"


def test_write_rotated_structure_keeps_the_title_and_rotates_the_positions(tmp_path: Path) -> None:
    gro = _write_gro(tmp_path)
    protein = _protein(gro, rotation_x=90.0, rotation_y=30.0)
    write_rotated_structure(protein, tmp_path)
    written = read_gro(rotated_structure_path(tmp_path, protein))
    original = read_gro(gro)
    assert written.title == original.title
    assert written.atom_prefixes == original.atom_prefixes
    np.testing.assert_allclose(written.positions, rotate_about_center(original.positions, 90.0, 30.0), atol=1e-3)


def test_input_str_includes_the_rotated_copy_for_a_rotated_protein(tmp_path: Path) -> None:
    gro = _write_gro(tmp_path)
    state = WizardState(working_directory=tmp_path)
    state.proteins = [_protein(gro, type_id=1), _protein(gro, type_id=2, rotation_x=10.0)]
    lines = build_input_str(state).splitlines()
    assert lines[0] == f"include {gro}"
    assert lines[1] == f"include {build_dir(tmp_path) / 'protein_type2_rotated.gro'}"


def test_pipeline_writes_each_rotated_structure_before_input_str(tmp_path: Path) -> None:
    gro = _write_gro(tmp_path)
    state = WizardState(working_directory=tmp_path, path_choice="analytical_shape", shape_type="Flat")
    state.proteins = [_protein(gro, type_id=1), _protein(gro, type_id=2, rotation_y=90.0)]
    labels = [step.label for step in build_pipeline(state)]
    rotation_index = labels.index("Write rotated structure of protein type 2")
    assert "Write rotated structure of protein type 1" not in labels
    assert rotation_index < labels.index("Write input.str")
    step = build_pipeline(state)[rotation_index]
    assert isinstance(step, PythonStep)
    step.action()
    assert (build_dir(tmp_path) / "protein_type2_rotated.gro").exists()


def _long_cloud() -> np.ndarray:
    rng = np.random.default_rng(3)
    direction = np.array([0.5, 0.4, 0.3])
    direction /= np.linalg.norm(direction)
    return np.outer(rng.uniform(-5.0, 5.0, 300), direction) + rng.normal(0.0, 0.3, (300, 3)) + 2.0


def _first_axis(positions: np.ndarray) -> np.ndarray:
    _values, vectors = np.linalg.eigh(np.cov(positions - positions.mean(axis=0), rowvar=False))
    axis = vectors[:, -1]
    return axis if axis[2] >= 0 else -axis


def test_aligning_with_zero_rotations_puts_the_principal_axis_on_z() -> None:
    positions = _long_cloud()
    aligned = rotate_about_center(positions, 0.0, 0.0, align_principal_axis=True)
    np.testing.assert_allclose(_first_axis(aligned), [0.0, 0.0, 1.0], atol=1e-9)
    np.testing.assert_allclose(aligned.mean(axis=0), positions.mean(axis=0))


def test_aligned_end_that_pointed_up_stays_on_top_and_180_about_x_flips_it() -> None:
    positions = _long_cloud()
    top = int(np.argmax((positions - positions.mean(axis=0)) @ [0.5, 0.4, 0.3]))
    aligned = rotate_about_center(positions, 0.0, 0.0, align_principal_axis=True)
    flipped = rotate_about_center(positions, 180.0, 0.0, align_principal_axis=True)
    center = positions.mean(axis=0)
    assert aligned[top, 2] - center[2] > 4.0
    np.testing.assert_allclose(flipped[:, 2] - center[2], -(aligned[:, 2] - center[2]), atol=1e-9)


def test_an_aligned_protein_is_built_from_its_own_copy(tmp_path: Path) -> None:
    gro = _write_gro(tmp_path)
    protein = _protein(gro, align_principal_axis=True)
    assert structure_path(protein, tmp_path) == tmp_path / "protein_type2_rotated.gro"
    write_rotated_structure(protein, tmp_path)
    written = read_gro(rotated_structure_path(tmp_path, protein)).positions
    expected = rotate_about_center(read_gro(gro).positions, 0.0, 0.0, align_principal_axis=True)
    np.testing.assert_allclose(written, expected, atol=1e-3)


def test_footprint_diameter_is_twice_the_widest_in_plane_reach() -> None:
    positions = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 9.0], [1.0, 3.0, -4.0], [1.0, -3.0, 0.0]])
    # In-plane center (1, 0): the widest reach is 3 nm, to (1, 3) and (1, -3); z is ignored.
    assert footprint_diameter(positions) == 6.0


def test_pipeline_checks_each_protein_types_count_right_after_placing_it(tmp_path: Path) -> None:
    gro = _write_gro(tmp_path)
    state = WizardState(working_directory=tmp_path, path_choice="analytical_shape", shape_type="Flat")
    state.proteins = [_protein(gro, type_id=1), _protein(gro, type_id=2)]
    labels = [step.label for step in build_pipeline(state)]
    for type_id in (1, 2):
        place = labels.index(f"Place protein Myprotein (type {type_id})")
        assert labels[place + 1] == f"Check every protein of type {type_id} fits"
