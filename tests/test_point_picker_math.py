"""Tests for widgets/point_picker_math.py - pure geometry, no Qt."""

from __future__ import annotations

import numpy as np
import pytest

from commic_overlay.widgets.point_picker_math import (
    bundle_to_representatives,
    closest_layer_mask,
    estimate_spacing,
    nearest_screen_point,
    points_in_view,
    points_within_pore,
    points_within_radius,
    select_visible_points,
    view_basis,
)

BOX = np.array([10.0, 10.0, 10.0])
FAR_LIMITS = np.array([[-1e6, 1e6]] * 3)


def _sphere(n: int = 4000, radius: float = 20.0) -> np.ndarray:
    """A Fibonacci lattice, evenly covering a sphere."""
    indices = np.arange(n) + 0.5
    polar = np.arccos(1 - 2 * indices / n)
    azimuth = np.pi * (1 + 5**0.5) * indices
    return radius * np.column_stack(
        [np.cos(azimuth) * np.sin(polar), np.sin(azimuth) * np.sin(polar), np.cos(polar)]
    )


def _sheet(side: int = 40) -> np.ndarray:
    x, y = np.meshgrid(np.arange(side, dtype=float), np.arange(side, dtype=float))
    return np.column_stack([x.ravel(), y.ravel(), np.sin(x.ravel() / 4.0) * 3.0])


def test_view_basis_is_orthonormal() -> None:
    right, up, toward_camera = view_basis(37.0, 12.0)
    basis = np.stack([right, up, toward_camera])
    assert np.allclose(basis @ basis.T, np.eye(3))


def test_view_basis_points_at_the_camera_from_above() -> None:
    _, _, toward_camera = view_basis(0.0, 90.0)
    assert np.allclose(toward_camera, [0.0, 0.0, 1.0])


def test_estimate_spacing_measures_a_regular_grid() -> None:
    x, y = np.meshgrid(np.arange(10.0) * 0.5, np.arange(10.0) * 0.5)
    coordinates = np.column_stack([x.ravel(), y.ravel(), np.zeros(100)])
    assert estimate_spacing(coordinates) == pytest.approx(0.5)


def test_closest_layer_hides_the_far_side_of_a_sphere() -> None:
    coordinates = _sphere()
    mask = closest_layer_mask(coordinates, 0.0, 90.0, estimate_spacing(coordinates))
    assert mask[coordinates[:, 2] > 10.0].all()
    assert not mask[coordinates[:, 2] < -10.0].any()


def test_closest_layer_shows_the_side_facing_a_rotated_camera() -> None:
    coordinates = _sphere()
    mask = closest_layer_mask(coordinates, 0.0, 0.0, estimate_spacing(coordinates))
    assert mask[coordinates[:, 0] > 10.0].all()
    assert not mask[coordinates[:, 0] < -10.0].any()


@pytest.mark.parametrize("elevation", [90.0, -90.0])
def test_closest_layer_keeps_a_wavy_open_sheet_from_both_sides(elevation: float) -> None:
    coordinates = _sheet()
    mask = closest_layer_mask(coordinates, 0.0, elevation, estimate_spacing(coordinates))
    assert mask.all()


def test_points_in_view_filters_by_limits() -> None:
    coordinates = np.array([[0.0, 0.0, 0.0], [5.0, 0.0, 0.0]])
    limits = np.array([[-1.0, 1.0], [-1.0, 1.0], [-1.0, 1.0]])
    assert points_in_view(coordinates, limits).tolist() == [True, False]


def test_bundle_passes_through_when_already_within_the_cap() -> None:
    coordinates = np.arange(30.0).reshape(10, 3)
    indices = np.arange(10)
    result = bundle_to_representatives(coordinates, indices, np.zeros(10, dtype=int), max_points=100)
    assert np.array_equal(result, indices)


def test_bundle_caps_at_max_points_with_distinct_real_points() -> None:
    coordinates = _sphere()
    indices = np.arange(len(coordinates))
    result = bundle_to_representatives(coordinates, indices, np.zeros(len(coordinates), dtype=int), max_points=100)
    assert len(result) <= 100
    assert len(set(result.tolist())) == len(result)
    assert set(result.tolist()) <= set(indices.tolist())


def test_bundle_uses_most_of_the_cap_on_a_flat_sheet() -> None:
    x, y = np.meshgrid(np.arange(100.0), np.arange(100.0))
    coordinates = np.column_stack([x.ravel(), y.ravel(), np.zeros(10000)])
    result = bundle_to_representatives(coordinates, np.arange(10000), np.zeros(10000, dtype=int), max_points=100)
    assert 50 <= len(result) <= 100


def test_bundle_picks_the_point_nearest_each_cluster_centroid() -> None:
    cluster_a = np.array([[0.0, 0.0, 0.0], [0.2, 0.0, 0.0], [-0.2, 0.0, 0.0], [0.0, 0.2, 0.0], [0.0, -0.2, 0.0]])
    cluster_b = np.full((5, 3), 10.0) + np.array([[0.1, 0, 0], [-0.1, 0, 0], [0, 0.1, 0], [0, -0.1, 0], [0, 0, 0]])
    coordinates = np.vstack([cluster_a, cluster_b])
    result = bundle_to_representatives(coordinates, np.arange(10), np.zeros(10, dtype=int), max_points=2)
    assert sorted(result.tolist()) == [0, 9]


def test_bundle_keeps_a_small_labelled_region_visible() -> None:
    x, y = np.meshgrid(np.arange(100.0), np.arange(100.0))
    coordinates = np.column_stack([x.ravel(), y.ravel(), np.zeros(10000)])
    labels = np.zeros(10000, dtype=int)
    labels[5050] = 7
    result = bundle_to_representatives(coordinates, np.arange(10000), labels, max_points=100)
    assert 5050 in result.tolist()


def test_select_visible_points_caps_and_stays_within_limits() -> None:
    coordinates = _sphere()
    labels = np.zeros(len(coordinates), dtype=int)
    limits = np.array([[-30.0, 30.0], [-30.0, 30.0], [0.0, 30.0]])
    result = select_visible_points(coordinates, labels, 0.0, 90.0, limits, estimate_spacing(coordinates))
    assert len(result) <= 100
    assert (coordinates[result, 2] >= 0.0).all()


def test_zooming_in_replaces_bundles_with_real_points() -> None:
    coordinates = _sheet()
    labels = np.zeros(len(coordinates), dtype=int)
    spacing = estimate_spacing(coordinates)
    zoomed_limits = np.array([[0.0, 4.5], [0.0, 4.5], [-10.0, 10.0]])
    zoomed_out = select_visible_points(coordinates, labels, 0.0, 90.0, FAR_LIMITS, spacing)
    zoomed_in = select_visible_points(coordinates, labels, 0.0, 90.0, zoomed_limits, spacing)
    assert len(zoomed_out) < len(coordinates)
    expected = np.nonzero(points_in_view(coordinates, zoomed_limits))[0]
    assert np.array_equal(np.sort(zoomed_in), expected)


def test_nearest_screen_point_finds_the_closest_row() -> None:
    assert nearest_screen_point(np.array([[0.0, 0.0], [10.0, 10.0]]), (9.0, 9.0), 5.0) == 1


def test_nearest_screen_point_respects_the_tolerance() -> None:
    assert nearest_screen_point(np.array([[0.0, 0.0]]), (9.0, 9.0), 5.0) is None


def test_nearest_screen_point_without_tolerance_always_finds_a_row() -> None:
    assert nearest_screen_point(np.array([[0.0, 0.0]]), (900.0, 900.0)) == 0


def test_nearest_screen_point_handles_no_points() -> None:
    assert nearest_screen_point(np.zeros((0, 2)), (0.0, 0.0), 5.0) is None


def test_points_within_radius_uses_minimum_image() -> None:
    coordinates = np.array([[0.5, 5.0, 5.0], [9.5, 5.0, 5.0], [5.0, 5.0, 5.0]])
    assert points_within_radius(coordinates, 0, 2.0, BOX).tolist() == [True, True, False]


def test_points_within_pore_measures_in_plane_distance() -> None:
    coordinates = np.array([[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [3.0, 0.0, 0.0], [0.0, 0.0, 4.0]])
    normals = np.tile([0.0, 0.0, 1.0], (4, 1))
    assert points_within_pore(coordinates, normals, 0, 2.0).tolist() == [True, True, False, True]


def test_points_within_pore_applies_the_normal_cutoff() -> None:
    coordinates = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 7.0]])
    normals = np.tile([0.0, 0.0, 1.0], (2, 1))
    assert points_within_pore(coordinates, normals, 0, 2.0).tolist() == [True, False]
