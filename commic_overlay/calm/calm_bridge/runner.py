"""Building CALM CLI argv, and launching it.

`CommandRunner`/`ParallelCommandRunner` are generic (own no CALM-specific
knowledge) and live in `commic_overlay/process_runner.py`, shared with
`ts2cg/ts2cg_bridge/runner.py` - re-exported here so existing imports of
`from ..calm_bridge.runner import CommandRunner` elsewhere in `calm/`
keep working unchanged.
"""

from __future__ import annotations

from ...process_runner import CommandRunner, ParallelCommandRunner
from .introspect import FieldSpec

__all__ = ["CommandRunner", "ParallelCommandRunner", "build_argv"]


def build_argv(argv_prefix: list[str], specs: list[FieldSpec], values: dict[str, object]) -> list[str]:
    """CALM's own argv, from one command's field specs and the Advanced window's current values.

    Same value-shape contract as CALM's own `CALM/gui/runner.py::build_argv`:
    a bool for "bool"/"bool_optional" fields, a list[str] for
    "multichoice"/"multi"/"append" fields, False/True/a non-empty str for
    "optional_flag_value" fields, a str for everything else. An
    empty/unset optional field is omitted from argv entirely - never
    passed as `--flag ""`.
    """
    argv = ["CALM", *argv_prefix]
    for spec in specs:
        value = values.get(spec.dest)
        if spec.kind == "bool":
            if value:
                argv.append(spec.flag)
        elif spec.kind == "bool_optional":
            long_name = spec.flag.lstrip("-")
            argv.append(f"--{long_name}" if value else f"--no-{long_name}")
        elif spec.kind in ("multichoice", "multi"):
            if value:
                assert isinstance(value, (list, tuple))
                argv.append(spec.flag)
                argv.extend(str(v) for v in value)
        elif spec.kind == "append":
            if value:
                assert isinstance(value, (list, tuple))
                for v in value:
                    argv.append(spec.flag)
                    argv.append(str(v))
        elif spec.kind == "optional_flag_value":
            if value is True:
                argv.append(spec.flag)
            elif isinstance(value, str) and value != "":
                argv.append(spec.flag)
                argv.append(value)
        else:
            if value is not None and str(value) != "":
                argv.append(spec.flag)
                argv.append(str(value))
    return argv
