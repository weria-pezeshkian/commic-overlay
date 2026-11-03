"""Pure geometry for the analytical-shape live preview.

Lightweight Python reimplementations of TS2CG's own C++ point-maker
midsurface formulas (`cpp/MembraneBuilder/{FlatPointMaker,Sphere,Cylinder,
SHGeneric1DPBCPointMaker}.cpp`) - just the shape each one describes, not
their full area-based point-density/triangulation algorithm - so the
preview can redraw instantly as a slider moves without spinning up a real
`TS2CG PCG -function analytical_shape -WPointDir` subprocess on every tick.
No Qt dependency here; `pages/analytical_shape_page.py` calls these and
feeds the result straight to its matplotlib canvas.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import product

import numpy as np

Box = tuple[float, float, float]
Mode = tuple[float, float, float]  # (A, n, Phi) - Phi in DEGREES, TS2CG's own convention
Corner = tuple[float, float, float]


def box_edges(box: Sequence[float]) -> list[tuple[Corner, Corner]]:
    """The 12 edges of the box spanning the origin to `box`, as (start, end) corner pairs."""
    corners = list(product((0.0, box[0]), (0.0, box[1]), (0.0, box[2])))
    return [
        (a, b) for i, a in enumerate(corners) for b in corners[i + 1:]
        if sum(1 for u, v in zip(a, b, strict=True) if u != v) == 1
    ]


def flat_preview(box: Box, thickness: float, resolution: int = 15) -> tuple[np.ndarray, np.ndarray]:
    """(upper, lower) point clouds for ShapeType Flat: two flat `box[0]`x`box[1]` sheets, `thickness`
    apart around the box's mid-height (`FlatPointMaker.cpp`'s `box[2]/2 + layer*H`)."""
    x = np.linspace(0, box[0], resolution)
    y = np.linspace(0, box[1], resolution)
    X, Y = np.meshgrid(x, y)
    middle = box[2] / 2
    upper = np.stack([X.ravel(), Y.ravel(), np.full(X.size, middle + thickness / 2)], axis=-1)
    lower = np.stack([X.ravel(), Y.ravel(), np.full(X.size, middle - thickness / 2)], axis=-1)
    return upper, lower


def _fibonacci_sphere(n: int) -> np.ndarray:
    """n unit vectors spread roughly evenly over a sphere - a simple, fast visual distribution,
    not TS2CG's own area-based one (`Sphere.cpp::CalculateArea_MakePoints`)."""
    indices = np.arange(n)
    phi = np.arccos(1 - 2 * (indices + 0.5) / n)
    golden_angle = np.pi * (3 - np.sqrt(5))
    theta = golden_angle * indices
    x = np.sin(phi) * np.cos(theta)
    y = np.sin(phi) * np.sin(theta)
    z = np.cos(phi)
    return np.stack([x, y, z], axis=-1)


def sphere_preview(box: Box, radius: float, thickness: float, resolution: int = 400) -> tuple[np.ndarray, np.ndarray]:
    """(upper, lower) point clouds for ShapeType Sphere: two concentric spheres centered in `box`,
    radius `radius +/- thickness/2` (`Sphere.cpp`'s own `R+H`/`R-H` convention for the outer/inner leaflet)."""
    center = np.array(box) / 2

    def shell(r: float) -> np.ndarray:
        return _fibonacci_sphere(resolution) * r + center

    return shell(radius + thickness / 2), shell(radius - thickness / 2)


def cylinder_preview(
    box: Box, radius: float, thickness: float, angular_resolution: int = 24, length_resolution: int = 20,
) -> tuple[np.ndarray, np.ndarray]:
    """(upper, lower) point clouds for ShapeType Cylinder: two concentric cylinders along the box's
    own z axis (`Cylinder.cpp`'s own convention: length = `box[2]`, radius `radius +/- thickness/2`)."""
    center_xy = np.array(box[:2]) / 2
    theta = np.linspace(0, 2 * np.pi, angular_resolution, endpoint=False)
    z = np.linspace(0, box[2], length_resolution)
    Theta, Z = np.meshgrid(theta, z)

    def shell(r: float) -> np.ndarray:
        x = center_xy[0] + r * np.cos(Theta)
        y = center_xy[1] + r * np.sin(Theta)
        return np.stack([x.ravel(), y.ravel(), Z.ravel()], axis=-1)

    return shell(radius + thickness / 2), shell(radius - thickness / 2)


def fourier_1d_preview(
    box: Box, modes: list[Mode], thickness: float, resolution: int = 40,
) -> tuple[np.ndarray, np.ndarray]:
    """(upper, lower) point clouds for ShapeType 1D_PBC_Fourier: a height-modulated sheet, varying
    only along x (uniform along y) - matches `SHGeneric1DPBCPointMaker::F`'s own midsurface formula:
    `z(x) = box[2]/2 + sum(A * cos(2*pi*n*x/box[0] + Phi))`, `Phi` converted from degrees to match
    `F`'s own `mode(2) * pi / 180`. Each leaflet is offset by a plain `+/- thickness/2` in z here,
    not `F`'s own local-normal offset - close enough for a schematic preview, not a physically exact one.
    """
    x = np.linspace(0, box[0], resolution)
    y = np.linspace(0, box[1], resolution)
    X, Y = np.meshgrid(x, y)
    Z = np.full_like(X, box[2] / 2)
    for amplitude, n, phi_degrees in modes:
        frequency = n * 2 * np.pi / box[0]
        phase = np.deg2rad(phi_degrees)
        Z = Z + amplitude * np.cos(frequency * X + phase)
    upper = np.stack([X.ravel(), Y.ravel(), (Z + thickness / 2).ravel()], axis=-1)
    lower = np.stack([X.ravel(), Y.ravel(), (Z - thickness / 2).ravel()], axis=-1)
    return upper, lower


def shape_preview(shape_type: str, params: dict[str, object]) -> tuple[np.ndarray, np.ndarray]:
    """Dispatches to the right `*_preview` function from `state.py`'s own `shape_params` dict.

    `params` keys match the real `[Shape Data]` field names (`Box`,
    `Thickness`, `Radius`, `Modes`) so a page's own parameter form can feed
    `state.shape_params` straight in with no renaming step.
    """
    box: Box = tuple(params.get("Box", (20.0, 20.0, 20.0)))  # type: ignore[assignment]
    thickness = float(params.get("Thickness", 3.8))  # type: ignore[arg-type]
    if shape_type == "Flat":
        return flat_preview(box, thickness)
    if shape_type == "Sphere":
        return sphere_preview(box, float(params.get("Radius", 5.0)), thickness)  # type: ignore[arg-type]
    if shape_type == "Cylinder":
        return cylinder_preview(box, float(params.get("Radius", 5.0)), thickness)  # type: ignore[arg-type]
    if shape_type == "1D_PBC_Fourier":
        modes = params.get("Modes", [])
        return fourier_1d_preview(box, modes, thickness)  # type: ignore[arg-type]
    raise ValueError(f"Unknown ShapeType: {shape_type!r}")
