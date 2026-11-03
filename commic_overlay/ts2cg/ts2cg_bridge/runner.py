"""Launching TS2CG CLI invocations.

`CommandRunner`/`ParallelCommandRunner` (the actual `QProcess` wrapper) are
shared, tool-agnostic infrastructure - see `commic_overlay/process_runner.py`'s
own docstring for why every TS2CG call goes through a real subprocess, same
as CALM's.
"""

from __future__ import annotations

from ...process_runner import CommandRunner, ParallelCommandRunner
from .introspect import build_argv

__all__ = ["CommandRunner", "ParallelCommandRunner", "build_argv"]
