"""Tests for ts2cg_bridge/shape_fields.py."""

from __future__ import annotations

from commic_overlay.ts2cg.ts2cg_bridge.input_str import _SHAPE_FIELD_ORDER
from commic_overlay.ts2cg.ts2cg_bridge.shape_fields import (
    SHAPE_FIELDS,
    advanced_fields,
    basic_fields,
    initial_values,
    shape_params,
)


def _names(fields: tuple) -> list[str]:
    return [field.name for field in fields]


def test_basic_fields_are_box_thickness_and_each_shapes_own_size() -> None:
    assert _names(basic_fields("Flat")) == ["Box", "Thickness"]
    assert _names(basic_fields("Sphere")) == ["Box", "Thickness", "Radius"]
    assert _names(basic_fields("Cylinder")) == ["Box", "Thickness", "Radius"]
    assert _names(basic_fields("1D_PBC_Fourier")) == ["Box", "Thickness"]


def test_cylinder_height_is_the_box_z() -> None:
    box = basic_fields("Cylinder")[0]
    assert "height" in box.sub_labels[2]


def test_basic_and_advanced_fields_cover_every_field_input_str_writes() -> None:
    for shape, order in _SHAPE_FIELD_ORDER.items():
        assert sorted(_names(basic_fields(shape)) + _names(advanced_fields(shape))) == sorted(order)


def test_defaults_match_their_sub_labels() -> None:
    for fields in SHAPE_FIELDS.values():
        for field in fields:
            assert len(field.defaults) == len(field.sub_labels)


def test_initial_values_carry_matching_fields_over_and_default_the_rest() -> None:
    values = initial_values("Sphere", {"Box": (20.0, 20.0, 30.0), "Thickness": 3.0, "Density": (2.0, 1.0)})
    assert values["Box"] == [20.0, 20.0, 30.0]
    assert values["Thickness"] == [3.0]
    assert values["Density"] == [2.0]
    assert values["Radius"] == [5.0]
    assert values["WallDensity"] == [1.0, 1.0]


def test_shape_params_stores_one_value_fields_as_scalars() -> None:
    params = shape_params({"Box": [10.0, 10.0, 10.0], "Thickness": [4.0]})
    assert params == {"Box": (10.0, 10.0, 10.0), "Thickness": 4.0}
