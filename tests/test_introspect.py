"""Tests for calm_bridge/introspect.py against CALM's own real installed parsers.

Deliberately not mocked - the whole point of this module is to stay in
sync with whatever CALM version is actually installed, so a test that
mocked out CALM's parsers would never catch a real drift.
"""

from __future__ import annotations

from commic_overlay.calm.calm_bridge.introspect import field_specs, full_command_spec, lipids_command_spec


def test_full_command_spec_has_the_expected_argv_prefix() -> None:
    spec = full_command_spec()
    assert spec.argv_prefix == ["analyze", "full"]


def test_lipids_command_spec_has_the_expected_argv_prefix() -> None:
    spec = lipids_command_spec()
    assert spec.argv_prefix == ["analyze", "lipids"]


def test_full_method_field_is_multichoice_with_six_values() -> None:
    specs = field_specs(full_command_spec().build_parser())
    method = next(s for s in specs if s.dest == "method")
    assert method.kind == "multichoice"
    assert method.choices == [
        "thickness", "Z_fitted", "mean", "gaussian", "principal", "principal_directions",
    ]


def test_full_remove_tmd_field_is_optional_flag_value() -> None:
    specs = field_specs(full_command_spec().build_parser())
    remove_tmd = next(s for s in specs if s.dest == "remove_tmd")
    assert remove_tmd.kind == "optional_flag_value"
    assert remove_tmd.flag == "--Remove-TMD"


def test_full_clear_field_is_bool_optional() -> None:
    specs = field_specs(full_command_spec().build_parser())
    clear = next(s for s in specs if s.dest == "clear")
    assert clear.kind == "bool_optional"
    assert clear.default is False


def test_full_rotate_field_is_plain_bool() -> None:
    specs = field_specs(full_command_spec().build_parser())
    rotate = next(s for s in specs if s.dest == "rotate")
    assert rotate.kind == "bool"


def test_full_structure_and_trajectory_are_required() -> None:
    specs = field_specs(full_command_spec().build_parser())
    by_dest = {s.dest: s for s in specs}
    assert by_dest["structure"].required is True
    assert by_dest["trajectory"].required is True
    assert by_dest["out"].required is True


def test_full_center_is_optional() -> None:
    specs = field_specs(full_command_spec().build_parser())
    center = next(s for s in specs if s.dest == "center")
    assert center.required is False
    assert center.kind == "text"


def test_lipids_field_is_multi_and_required() -> None:
    specs = field_specs(lipids_command_spec().build_parser())
    lipids = next(s for s in specs if s.dest == "lipids")
    assert lipids.kind == "multi"
    assert lipids.required is True


def test_no_fire_and_exit_actions_leak_into_field_specs() -> None:
    # --man (core/manual.py::add_manual) is a fire-and-exit action with
    # default=argparse.SUPPRESS - field_specs must skip it, same as -h.
    for spec in field_specs(full_command_spec().build_parser()):
        assert spec.dest not in ("help", "man")
