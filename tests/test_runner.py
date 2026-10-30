"""Tests for calm_bridge/runner.py::build_argv - pure logic, synthetic FieldSpecs.

Mirrors CALM's own CALM/gui/runner.py::build_argv contract exactly (this
module is an independent reimplementation of it) - these cases cover one
representative FieldSpec per `kind`.
"""

from __future__ import annotations

from commic_overlay.calm.calm_bridge.introspect import FieldSpec
from commic_overlay.calm.calm_bridge.runner import build_argv


def _spec(dest: str, flag: str, kind: str, choices: list[str] | None = None) -> FieldSpec:
    return FieldSpec(
        dest=dest, option_strings=[flag], flag=flag, kind=kind,
        help="", required=False, default=None, choices=choices,
    )


def test_bool_emits_flag_only_when_true() -> None:
    spec = _spec("rotate", "--rotate", "bool")
    assert build_argv([], [spec], {"rotate": True}) == ["CALM", "--rotate"]
    assert build_argv([], [spec], {"rotate": False}) == ["CALM"]
    assert build_argv([], [spec], {}) == ["CALM"]


def test_bool_optional_always_emits_explicit_flag_or_no_flag() -> None:
    spec = _spec("clear", "--clear", "bool_optional")
    assert build_argv([], [spec], {"clear": True}) == ["CALM", "--clear"]
    assert build_argv([], [spec], {"clear": False}) == ["CALM", "--no-clear"]


def test_multichoice_emits_flag_once_followed_by_all_values() -> None:
    spec = _spec("method", "--method", "multichoice", choices=["mean", "gaussian"])
    argv = build_argv([], [spec], {"method": ["mean", "gaussian"]})
    assert argv == ["CALM", "--method", "mean", "gaussian"]


def test_multichoice_omitted_when_empty() -> None:
    spec = _spec("method", "--method", "multichoice", choices=["mean"])
    assert build_argv([], [spec], {"method": []}) == ["CALM"]
    assert build_argv([], [spec], {}) == ["CALM"]


def test_multi_emits_flag_once_followed_by_all_values() -> None:
    spec = _spec("lipids", "--lipids", "multi")
    argv = build_argv([], [spec], {"lipids": ["POPC", "CHOL"]})
    assert argv == ["CALM", "--lipids", "POPC", "CHOL"]


def test_append_emits_flag_once_per_value() -> None:
    spec = _spec("replica", "--replica", "append")
    argv = build_argv([], [spec], {"replica": ["a", "b"]})
    assert argv == ["CALM", "--replica", "a", "--replica", "b"]


def test_optional_flag_value_bare_true_emits_flag_only() -> None:
    spec = _spec("remove_tmd", "--Remove-TMD", "optional_flag_value")
    argv = build_argv([], [spec], {"remove_tmd": True})
    assert argv == ["CALM", "--Remove-TMD"]


def test_optional_flag_value_with_string_emits_flag_and_value() -> None:
    spec = _spec("remove_tmd", "--Remove-TMD", "optional_flag_value")
    argv = build_argv([], [spec], {"remove_tmd": "name BB SC1"})
    assert argv == ["CALM", "--Remove-TMD", "name BB SC1"]


def test_optional_flag_value_false_omits_entirely() -> None:
    spec = _spec("remove_tmd", "--Remove-TMD", "optional_flag_value")
    assert build_argv([], [spec], {"remove_tmd": False}) == ["CALM"]
    assert build_argv([], [spec], {"remove_tmd": ""}) == ["CALM"]


def test_text_field_emits_flag_and_stringified_value() -> None:
    spec = _spec("center", "--center", "text")
    argv = build_argv([], [spec], {"center": "protein"})
    assert argv == ["CALM", "--center", "protein"]


def test_text_field_numeric_value_is_stringified() -> None:
    spec = _spec("Step", "--Step", "text")
    argv = build_argv([], [spec], {"Step": 2})
    assert argv == ["CALM", "--Step", "2"]


def test_text_field_empty_or_none_is_omitted_not_passed_as_empty_string() -> None:
    spec = _spec("center", "--center", "text")
    assert build_argv([], [spec], {"center": ""}) == ["CALM"]
    assert build_argv([], [spec], {"center": None}) == ["CALM"]
    assert build_argv([], [spec], {}) == ["CALM"]


def test_argv_prefix_is_included_verbatim() -> None:
    argv = build_argv(["analyze", "full"], [], {})
    assert argv == ["CALM", "analyze", "full"]


def test_realistic_combination_in_field_order() -> None:
    specs = [
        _spec("trajectory", "--trajectory", "text"),
        _spec("structure", "--structure", "text"),
        _spec("out", "--out", "text"),
        _spec("rotate", "--rotate", "bool"),
        _spec("clear", "--clear", "bool_optional"),
    ]
    values = {
        "trajectory": "traj.xtc", "structure": "struct.tpr", "out": "/tmp/out",
        "rotate": False, "clear": True,
    }
    argv = build_argv(["analyze", "full"], specs, values)
    assert argv == [
        "CALM", "analyze", "full",
        "--trajectory", "traj.xtc", "--structure", "struct.tpr", "--out", "/tmp/out",
        "--clear",
    ]
