"""Tests for ts2cg_bridge/python_tools.py against the real TS2CG package, when installed."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from commic_overlay.ts2cg.ts2cg_bridge.python_tools import load_point, python_tool_argv

OUTER_HEADER = "Box 10 10 10\n< Point NoPoints 1>\n< id domain_id area X Y Z >\n< Outer >\n"
OUTER_ROW = " ".join(["0"] * 18) + "\n" + " ".join(["1"] * 18) + "\n"
INNER_HEADER = "< Point NoPoints 1>\n< id domain_id area X Y Z >\n< Inner >\n"


def test_python_tool_argv_runs_this_module_as_a_script() -> None:
    argv = python_tool_argv("DOP", "--point-dir", "point")
    assert argv[:2] == [sys.executable, "-P"]
    assert Path(argv[2]).name == "python_tools.py"
    assert argv[3:] == ["DOP", "--point-dir", "point"]


def test_load_point_reads_a_directory_holding_one_inclusion(tmp_path: Path) -> None:
    pytest.importorskip("TS2CG")
    (tmp_path / "OuterBM.dat").write_text(OUTER_HEADER + OUTER_ROW)
    (tmp_path / "InnerBM.dat").write_text(INNER_HEADER + OUTER_ROW)
    (tmp_path / "IncData.dat").write_text("< Inclusion NoInc 1 >\n< id typeid pointid lx ly lz >\n0 3 1 1 0 0\n")
    membrane = load_point(tmp_path)
    assert len(membrane.inclusions) == 1
    assert membrane.inclusions.get_by_type(3)[0]["point_id"] == 1
    assert np.allclose(membrane.inclusions[0]["orientation"], [1.0, 0.0, 0.0])


def test_load_point_reads_a_directory_holding_two_inclusions(tmp_path: Path) -> None:
    pytest.importorskip("TS2CG")
    (tmp_path / "OuterBM.dat").write_text(OUTER_HEADER + OUTER_ROW)
    (tmp_path / "InnerBM.dat").write_text(INNER_HEADER + OUTER_ROW)
    (tmp_path / "IncData.dat").write_text(
        "< Inclusion NoInc 2 >\n< id typeid pointid lx ly lz >\n0 3 1 1 0 0\n1 3 0 1 0 0\n"
    )
    assert len(load_point(tmp_path).inclusions) == 2
