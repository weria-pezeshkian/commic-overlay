"""Tests for ts2cg_bridge/shape_preview.py."""

from __future__ import annotations

import numpy as np

from commic_overlay.ts2cg.ts2cg_bridge.shape_preview import (
    box_edges,
    cylinder_preview,
    flat_preview,
    fourier_1d_preview,
    shape_preview,
    sphere_preview,
)


def test_flat_preview_upper_and_lower_are_thickness_apart_around_mid_box() -> None:
    upper, lower = flat_preview((20.0, 20.0, 20.0), thickness=4.0)
    assert np.allclose(upper[:, 2], 12.0)
    assert np.allclose(lower[:, 2], 8.0)
    assert upper[:, 0].max() <= 20.0 and upper[:, 0].min() >= 0.0


def test_sphere_preview_shells_sit_at_radius_plus_minus_half_thickness() -> None:
    box = (30.0, 30.0, 30.0)
    upper, lower = sphere_preview(box, radius=5.0, thickness=4.0, resolution=200)
    center = np.array(box) / 2
    upper_radii = np.linalg.norm(upper - center, axis=1)
    lower_radii = np.linalg.norm(lower - center, axis=1)
    assert np.allclose(upper_radii, 7.0, atol=1e-6)
    assert np.allclose(lower_radii, 3.0, atol=1e-6)


def test_cylinder_preview_shells_sit_at_radius_plus_minus_half_thickness_and_span_box_z() -> None:
    box = (30.0, 30.0, 50.0)
    upper, lower = cylinder_preview(box, radius=5.0, thickness=4.0)
    center_xy = np.array(box[:2]) / 2
    upper_radii = np.linalg.norm(upper[:, :2] - center_xy, axis=1)
    assert np.allclose(upper_radii, 7.0, atol=1e-6)
    assert upper[:, 2].max() == 50.0
    assert upper[:, 2].min() == 0.0


def test_fourier_1d_preview_flat_with_no_modes_matches_flat_preview() -> None:
    box = (20.0, 20.0, 10.0)
    upper, lower = fourier_1d_preview(box, modes=[], thickness=4.0, resolution=10)
    # No modes -> z(x) == box[2]/2 everywhere, same as a flat sheet centered mid-box.
    assert np.allclose(upper[:, 2], 5.0 + 2.0)
    assert np.allclose(lower[:, 2], 5.0 - 2.0)


def test_fourier_1d_preview_one_mode_oscillates_with_the_right_period() -> None:
    box = (20.0, 10.0, 0.0)
    upper, _lower = fourier_1d_preview(box, modes=[(1.0, 1.0, 0.0)], thickness=0.0, resolution=21)
    # n=1 over box[0]=20 -> one full period across x; amplitude 1, phase 0 -> z(0) peaks at +1.
    x0_mask = upper[:, 0] == 0.0
    assert np.allclose(upper[x0_mask, 2], 1.0, atol=1e-6)


def test_shape_preview_dispatches_by_shape_type() -> None:
    params = {"Box": (20.0, 20.0, 20.0), "Thickness": 4.0, "Radius": 5.0}
    upper_direct, _ = sphere_preview((20.0, 20.0, 20.0), 5.0, 4.0)
    upper_dispatched, _ = shape_preview("Sphere", params)
    assert upper_direct.shape == upper_dispatched.shape


def test_shape_preview_raises_on_unknown_shape_type() -> None:
    import pytest

    with pytest.raises(ValueError, match="Unknown ShapeType"):
        shape_preview("Torus", {})


def test_box_edges_are_the_twelve_axis_aligned_edges_of_the_box() -> None:
    edges = box_edges((2.0, 3.0, 4.0))
    assert len(edges) == 12
    lengths = sorted(float(np.linalg.norm(np.subtract(end, start))) for start, end in edges)
    assert lengths == [2.0] * 4 + [3.0] * 4 + [4.0] * 4
