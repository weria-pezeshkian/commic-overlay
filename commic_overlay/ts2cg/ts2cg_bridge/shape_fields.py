"""The `[Shape Data]` fields of each analytical ShapeType, as the Analytical Shape page shows them.

Field names, per-field value counts, and defaults are verified against TS2CG's C++ parsers
(`cpp/MembraneBuilder/{FlatPointMaker,Sphere,Cylinder,SHGeneric1DPBCPointMaker}.cpp`'s
`Line.at(0)==...`/`Line.size()<N` checks and constructor defaults), not the header
doc-comments, which are copy-pasted across files. Flat's "Density" line carries two values
(density, wall density) with no WallDensity keyword, while Sphere/Cylinder/1D_PBC_Fourier
have a one-value Density and a separate two-value WallDensity.

Fields marked `advanced` go in the page's Advanced shape settings dialog; the others are
always shown. Cylinder has no length field: `Cylinder.cpp` runs the tube through the whole
box height, `Box` Z. The 1D_PBC_Fourier Mode rows are repeatable and handled by the page.
"""

from __future__ import annotations

from dataclasses import dataclass

_WALL_NOTE = "Used only with Add wall beads on the Summary page."


@dataclass(frozen=True)
class ShapeField:
    name: str  # the [Shape Data] keyword
    label: str
    sub_labels: tuple[str, ...]
    defaults: tuple[float, ...]
    minimum: float = -10_000.0
    maximum: float = 10_000.0
    advanced: bool = False
    help: str = ""


def _box(defaults: tuple[float, float, float], z_label: str = "Z") -> ShapeField:
    return ShapeField(
        "Box", "Box (nm)", ("X", "Y", z_label), defaults, minimum=0.1,
        help="Simulation box edge lengths.",
    )


_THICKNESS = ShapeField(
    "Thickness", "Thickness (nm)", ("Thickness",), (4.0,), minimum=0.0,
    help="Distance between the two leaflets' point layers.",
)
_RADIUS = ShapeField(
    "Radius", "Radius (nm)", ("Radius",), (5.0,), minimum=0.0,
    help="Radius of the membrane midplane, between the two leaflets.",
)
_DENSITY = ShapeField(
    "Density", "Point density", ("Points per nm²",), (2.5,), minimum=0.01, advanced=True,
    help="Points per nm² on each leaflet.",
)
_DL = ShapeField(
    "DL", "DL (nm)", ("DL",), (0.0,), advanced=True,
    help="Shifts every point along its normal by this distance.",
)
_WALL_RANGE = ShapeField(
    "WallRange", "Wall range", ("x0", "x1", "y0", "y1"), (0.0, 1.0, 0.0, 1.0), minimum=0.0, maximum=1.0,
    advanced=True, help=f"The part of the box the wall covers in x and y, as fractions of the box. {_WALL_NOTE}",
)


def _wall_density(sub_labels: tuple[str, str]) -> ShapeField:
    return ShapeField(
        "WallDensity", "Wall density", sub_labels, (1.0, 1.0), minimum=0.01, advanced=True,
        help=f"Wall points per nm² on each side. {_WALL_NOTE}",
    )


SHAPE_FIELDS: dict[str, tuple[ShapeField, ...]] = {
    "Flat": (
        _box((10.0, 10.0, 10.0)),
        _THICKNESS,
        _WALL_RANGE,
        ShapeField(
            "Density", "Point density", ("Points per nm²", "Wall points per nm²"), (2.0, 1.0), minimum=0.01,
            advanced=True,
            help="Points per nm² on each leaflet, then on the wall. The wall value is used only with "
            "Add wall beads on the Summary page.",
        ),
    ),
    "Sphere": (
        _box((15.0, 15.0, 15.0)),
        _THICKNESS,
        _RADIUS,
        _DENSITY,
        _wall_density(("Upper", "Inner")),
        _DL,
    ),
    "Cylinder": (
        _box((15.0, 15.0, 15.0), z_label="Z = height"),
        _THICKNESS,
        _RADIUS,
        _DENSITY,
        _wall_density(("Upper", "Inner")),
        _DL,
    ),
    "1D_PBC_Fourier": (
        _box((10.0, 10.0, 10.0)),
        _THICKNESS,
        _WALL_RANGE,
        _DENSITY,
        _wall_density(("Upper", "Lower")),
    ),
}


def basic_fields(shape: str) -> tuple[ShapeField, ...]:
    return tuple(f for f in SHAPE_FIELDS[shape] if not f.advanced)


def advanced_fields(shape: str) -> tuple[ShapeField, ...]:
    return tuple(f for f in SHAPE_FIELDS[shape] if f.advanced)


def initial_values(shape: str, existing: dict[str, object]) -> dict[str, list[float]]:
    """Each field's values for `shape`: from `existing` (state.shape_params, where a one-value
    field is a plain scalar) by field name where present, the field's defaults elsewhere."""
    values: dict[str, list[float]] = {}
    for field in SHAPE_FIELDS[shape]:
        current = list(field.defaults)
        stored = existing.get(field.name)
        if stored is not None:
            stored_values = stored if isinstance(stored, (tuple, list)) else (stored,)
            for i, value in enumerate(stored_values[: len(current)]):
                current[i] = float(value)
        values[field.name] = current
    return values


def shape_params(values: dict[str, list[float]]) -> dict[str, object]:
    """`state.shape_params` for `values`: a one-value field as a plain scalar, others as tuples
    (the form `shape_preview.py` and `input_str.py` read)."""
    return {name: v[0] if len(v) == 1 else tuple(v) for name, v in values.items()}
