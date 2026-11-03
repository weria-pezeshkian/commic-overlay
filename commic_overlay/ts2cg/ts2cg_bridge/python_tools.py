"""Launching TS2CG's Python tools so a point directory holding one inclusion loads.

`Point` reads `IncData.dat` through `np.loadtxt`, which returns a 1-D array for a one-row
file, and `Inclusion._process_data` then raises IndexError on `data.shape[1]`. `INU` and
`DOP` run this file as a script and in-process loads go through `load_point`; both repair
the array shape first.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from functools import cache, partialmethod
from pathlib import Path
from typing import Any


def python_tool_argv(module: str, *arguments: str) -> list[str]:
    """Argv running TS2CG's `module` through this file. `-P` leaves this file's directory
    off `sys.path`, which keeps its sibling modules clear of TS2CG's own imports."""
    return [sys.executable, "-P", str(Path(__file__).resolve()), module, *arguments]


def _process_rows(inclusion: Any, original: Callable[[Any, Any], None], data: Any) -> None:
    """Gives one-row `data` the (6, 1) shape `original` indexes."""
    if data is not None and data.ndim == 1 and data.size > 0:
        data = data[:, None]
    original(inclusion, data)


@cache
def _repair_inclusion_loading() -> None:
    from TS2CG.core.inclusion import Inclusion

    Inclusion._process_data = partialmethod(_process_rows, Inclusion._process_data)


def load_point(point_dir: Path) -> Any:
    """`TS2CG.core.point.Point(point_dir)` with one-inclusion directories loading."""
    _repair_inclusion_loading()
    from TS2CG.core.point import Point

    return Point(point_dir)


def main() -> None:
    _repair_inclusion_loading()
    from TS2CG.run_modules import run_python_module

    run_python_module(sys.argv[1], sys.argv[2:])


if __name__ == "__main__":
    main()
