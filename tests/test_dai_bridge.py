"""Tests for ts2cg_bridge/dai_bridge.py - fake membranes, no real TS2CG call."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from commic_overlay.ts2cg.state import DomainOp
from commic_overlay.ts2cg.ts2cg_bridge.dai_bridge import (
    apply_circular_op,
    apply_circular_op_to_directory,
    check_points_match_preview,
    nearest_point_ids,
    outer_center_ids,
    write_exclusions,
)

BOX = np.array([10.0, 10.0, 10.0])


class _FakeLeaflet:
    def __init__(self, coordinates: np.ndarray) -> None:
        self.coordinates = coordinates


class _FakeInclusions:
    def __init__(self, rows: list[dict[str, int]]) -> None:
        self.rows = rows

    def get_by_type(self, type_id: int) -> list[dict[str, int]]:
        return [row for row in self.rows if row["type_id"] == type_id]


class _FakeExclusions:
    def __init__(self) -> None:
        self.exclusions: list[dict[str, float]] = [{"id": 0, "point_id": 3, "radius": 1.0}]

    def add_pore(self, point_id: int, radius: float = 1.0) -> None:
        self.exclusions.append({"id": len(self.exclusions), "point_id": point_id, "radius": radius})


class _FakeMembrane:
    def __init__(self, outer: np.ndarray, inner: np.ndarray | None = None) -> None:
        self.outer = _FakeLeaflet(outer)
        self.inner = None if inner is None else _FakeLeaflet(inner)
        self.monolayer = inner is None
        self.box = BOX
        self.inclusions = _FakeInclusions([{"type_id": 1, "point_id": 2}, {"type_id": 2, "point_id": 0}])
        self.exclusions = _FakeExclusions()
        self.saved: list[tuple[Path, bool]] = []

    def save(self, path: Path, backup: bool = True) -> None:
        self.saved.append((path, backup))


class _RecordingAssign:
    """Records each `assign` call along with the coordinates it saw."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[int]]] = []
        self.seen_coordinates: list[np.ndarray] = []

    def __call__(self, membrane: _FakeMembrane, op: DomainOp, centers: list[int], leaflet: str) -> None:
        self.calls.append((leaflet, centers))
        self.seen_coordinates.append(getattr(membrane, leaflet).coordinates.copy())


def _sheet(z: float, n: int = 4) -> np.ndarray:
    return np.column_stack([np.arange(n, dtype=float), np.zeros(n), np.full(n, z)])


def test_nearest_point_ids_uses_minimum_image() -> None:
    coordinates = np.array([[1.0, 5.0, 5.0], [9.5, 5.0, 5.0]])
    assert nearest_point_ids(coordinates, np.array([[0.2, 5.0, 5.0]]), BOX) == [1]


def test_outer_center_ids_of_point_op_are_its_point_ids() -> None:
    op = DomainOp(kind="dai_point", point_ids=[3, 7])
    assert outer_center_ids(_FakeMembrane(_sheet(1.0)), op) == [3, 7]


def test_outer_center_ids_of_inclusion_op_are_that_types_inclusions() -> None:
    op = DomainOp(kind="dai_inclusion", protein_type_id=1)
    assert outer_center_ids(_FakeMembrane(_sheet(1.0)), op) == [2]


def test_apply_circular_op_both_maps_inner_centers_to_nearest_inner_points() -> None:
    outer = np.array([[1.0, 1.0, 5.0], [8.0, 8.0, 5.0]])
    inner = np.array([[8.1, 8.0, 3.0], [5.0, 5.0, 3.0], [1.0, 1.1, 3.0]])
    assign = _RecordingAssign()
    apply_circular_op(_FakeMembrane(outer, inner), DomainOp(kind="dai_point", point_ids=[1]), assign=assign)
    assert assign.calls == [("outer", [1]), ("inner", [0])]


def test_apply_circular_op_outer_touches_only_the_outer_leaflet() -> None:
    assign = _RecordingAssign()
    op = DomainOp(kind="dai_point", leaflet="outer", point_ids=[0])
    apply_circular_op(_FakeMembrane(_sheet(5.0), _sheet(3.0)), op, assign=assign)
    assert assign.calls == [("outer", [0])]


def test_apply_circular_op_inner_touches_only_the_inner_leaflet() -> None:
    assign = _RecordingAssign()
    op = DomainOp(kind="dai_point", leaflet="inner", point_ids=[2])
    apply_circular_op(_FakeMembrane(_sheet(5.0), _sheet(3.0)), op, assign=assign)
    assert assign.calls == [("inner", [2])]


def test_apply_circular_op_monolayer_uses_the_outer_leaflet_whatever_is_requested() -> None:
    assign = _RecordingAssign()
    op = DomainOp(kind="dai_point", leaflet="inner", point_ids=[1])
    apply_circular_op(_FakeMembrane(_sheet(5.0)), op, assign=assign)
    assert assign.calls == [("outer", [1])]


def test_apply_circular_op_wraps_coordinates_for_the_call_and_restores_them() -> None:
    outer = np.array([[12.5, 1.0, 5.0], [1.0, 1.0, 5.0]])
    membrane = _FakeMembrane(outer.copy())
    assign = _RecordingAssign()
    apply_circular_op(membrane, DomainOp(kind="dai_point", point_ids=[0]), assign=assign)
    assert assign.seen_coordinates[0][0, 0] == pytest.approx(2.5)
    assert np.array_equal(membrane.outer.coordinates, outer)


def test_apply_circular_op_to_directory_saves_without_backup(tmp_path: Path) -> None:
    membrane = _FakeMembrane(_sheet(5.0), _sheet(3.0))
    op = DomainOp(kind="dai_point", leaflet="outer", domain_id=1, point_ids=[])
    apply_circular_op_to_directory(tmp_path, op, load=lambda _path: membrane)
    assert membrane.saved == [(tmp_path, False)]


def test_write_exclusions_keeps_existing_rows_and_writes_fractional_radii(tmp_path: Path) -> None:
    ops = [
        DomainOp(kind="exclusion", radius=2.75, point_ids=[42]),
        DomainOp(kind="exclusion", radius=0.5, point_ids=[7]),
    ]
    write_exclusions(tmp_path, ops, load=lambda _path: _FakeMembrane(_sheet(5.0)))
    lines = (tmp_path / "ExcData.dat").read_text().splitlines()
    assert lines[0] == "< Exclusion NoExc 3 >"
    assert [line.split() for line in lines[2:]] == [["0", "3", "1.000"], ["1", "42", "2.750"], ["2", "7", "0.500"]]


def test_check_points_match_preview_accepts_identical_points(tmp_path: Path) -> None:
    check_points_match_preview(tmp_path, tmp_path, load=lambda _path: _FakeMembrane(_sheet(5.0)))


def test_check_points_match_preview_rejects_a_different_point_count(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    membranes = {run_dir: _FakeMembrane(_sheet(5.0, 4)), tmp_path: _FakeMembrane(_sheet(5.0, 5))}
    with pytest.raises(RuntimeError, match="pick them again"):
        check_points_match_preview(run_dir, tmp_path, load=membranes.__getitem__)


def test_check_points_match_preview_rejects_moved_points(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    membranes = {run_dir: _FakeMembrane(_sheet(5.0)), tmp_path: _FakeMembrane(_sheet(6.0))}
    with pytest.raises(RuntimeError, match="pick them again"):
        check_points_match_preview(run_dir, tmp_path, load=membranes.__getitem__)
