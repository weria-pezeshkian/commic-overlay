"""Introspection of CALM's own installed argparse parsers.

Reimplements the same FieldSpec/field_specs technique CALM's own `CALM-gui`
app already uses (`CALM/gui/introspect.py`) - independently, against
CALM's plain parser-builder functions (`_build_full_parser`/
`_build_lipids_parser`), not by importing anything from CALM's `gui`
package. Those builder functions are ordinary, side-effect-free factories
- part of the installed CALM package like any other - this overlay just
reads the `argparse.ArgumentParser` they build instead of only ever
calling `parser.parse_args()` on it.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_REQUIRED_GROUP_TITLE = "Required arguments"
_OPTIONAL_GROUP_TITLE = "Optional arguments"

# FieldSpec.dest values a wizard page owns its own widget for - pre-filled
# into the Advanced window from WizardState, and written straight back to
# that same WizardState field when Apply is clicked (see
# advanced_window.py's _write_back_wizard_fields), not stored as a
# separate override: editing one of these in Advanced and applying it is
# the same as if the owning wizard page's own widget had changed, so
# going back to that page afterward shows the new value, and any later
# wizard-page edit naturally wins again (there is exactly one place each
# of these values actually lives).
WIZARD_STATE_DESTS = frozenset(
    {"trajectory", "structure", "index", "Step", "center", "rotate", "remove_tmd", "lipids"}
)

# FieldSpec.dest values that are neither wizard-state-backed nor a free
# "extra" override: `out` is always computed from the working directory
# (see calm_bridge/outputs.py) - letting it diverge would break the
# Results page, which looks for output under that same fixed path
# regardless of what `-o` a run was actually given. `clear` is always
# forced on by the wizard's own Run (see outputs.py's own docstring) -
# no wizard page exposes a toggle for it, so there is nothing for an
# Advanced edit to "go back and see" either. Both are simply excluded
# from the Advanced window's Apply in either direction.
EXCLUDED_FROM_ADVANCED_DESTS = frozenset({"out", "clear"})


@dataclass
class FieldSpec:
    """One argparse Action's shape, as the Advanced window's form generator needs it.

    `kind` is one of:
    - "bool" - store_true/store_false: a plain checkbox.
    - "bool_optional" - BooleanOptionalAction (e.g. `--clear`): a checkbox
      that emits an explicit `--flag`/`--no-flag` either way.
    - "choice" - `choices` given, single value: a single-select dropdown.
    - "multichoice" - `choices` given, `nargs` in ("+", "*"): several of
      the fixed choices at once (e.g. `--method`).
    - "multi" - `nargs` in ("+", "*"), no `choices` (e.g. `--lipids`): a
      text entry, space-separated, same syntax as the CLI itself.
    - "append" - an `action="append"` flag: a text entry, space-separated
      like "multi", but the flag itself repeats once per value when built
      back into argv, not once with every value trailing.
    - "optional_flag_value" - `nargs="?"` with `const=True` (`--Remove-TMD`):
      a three-state flag - omitted (False), given bare (True), or given
      with a value (a selection string).
    - "text" - everything else (str/int/float/a custom `type=` callable):
      a plain text entry. The real CLI subprocess validates the value for
      real when it actually runs.

    `required` is not simply the action's own argparse `required=` flag:
    several CALM flags are `required=False` individually but part of a
    broader either/or argparse itself can't express (`--sft` vs.
    `-f/-s/-n` in `analyze full`) - the command's own parser already says
    so by which argument group it put the flag in, so that group is
    preferred when present.
    """

    dest: str
    option_strings: list[str]
    flag: str
    kind: str
    help: str
    required: bool
    default: Any
    choices: list[str] | None = None


def field_specs(parser: argparse.ArgumentParser) -> list[FieldSpec]:
    """Every user-facing argument `parser` accepts, as FieldSpecs.

    Skips fire-and-exit actions (-h/--help, --man, -v/--version,
    SUPPRESS-defaulted) and positionals (no CALM command this overlay
    drives has one).
    """
    group_titles = {
        id(action): group.title for group in parser._action_groups for action in group._group_actions
    }
    return [
        _field_spec(action, group_titles.get(id(action)))
        for action in parser._actions
        if action.option_strings and action.default is not argparse.SUPPRESS
    ]


def _field_spec(action: argparse.Action, group_title: str | None) -> FieldSpec:
    flag = next((s for s in action.option_strings if s.startswith("--")), action.option_strings[-1])

    if isinstance(action, argparse.BooleanOptionalAction):
        kind = "bool_optional"
    elif isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
        kind = "bool"
    elif isinstance(action, argparse._AppendAction):
        kind = "append"
    elif action.choices is not None and action.nargs in ("+", "*"):
        kind = "multichoice"
    elif action.choices is not None:
        kind = "choice"
    elif action.nargs == "?" and action.const is True:
        kind = "optional_flag_value"
    elif action.nargs in ("+", "*"):
        kind = "multi"
    else:
        kind = "text"

    if group_title == _REQUIRED_GROUP_TITLE:
        required = True
    elif group_title == _OPTIONAL_GROUP_TITLE:
        required = False
    else:
        required = bool(getattr(action, "required", False))

    return FieldSpec(
        dest=action.dest,
        option_strings=list(action.option_strings),
        flag=flag,
        kind=kind,
        help=action.help or "",
        required=required,
        default=action.default,
        choices=[str(c) for c in action.choices] if action.choices is not None else None,
    )


@dataclass
class CommandSpec:
    """One CALM leaf command's identity: its label, the argv prefix CALM itself needs
    (e.g. `["analyze", "full"]`), and its own parser builder."""

    label: str
    argv_prefix: list[str]
    build_parser: Callable[[], argparse.ArgumentParser]


def full_command_spec() -> CommandSpec:
    # Deferred import: CALM's presence is already confirmed at app startup
    # (see main.py), not at module import time - this module itself must
    # stay importable (e.g. for tests that mock it out) even before that
    # check has run.
    from CALM.analyze.full import _build_full_parser

    return CommandSpec("Full", ["analyze", "full"], _build_full_parser)


def lipids_command_spec() -> CommandSpec:
    from CALM.analyze.lipids import _build_lipids_parser

    return CommandSpec("Lipids", ["analyze", "lipids"], _build_lipids_parser)
