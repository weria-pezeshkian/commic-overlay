"""Saving a tool's wizard state to a JSON config file and loading it back.

The file holds `{"tool": ..., "format_version": ..., "state": {...}}`, the state being every
field of the tool's `WizardState` except its runtime-only ones. Loading rebuilds each field
from the dataclass's type hints: a `Path` from its string, an `int` dictionary key from its
JSON string, a set from its list, nested dataclasses field by field. A value typed `object`
(shape parameters, Advanced-window overrides) comes back with every list as a tuple, the form
those values take in the wizard. A field the file leaves out keeps its default.
"""

from __future__ import annotations

import dataclasses
import json
import types
import typing
from pathlib import Path
from typing import Any

FORMAT_VERSION = 1


class ConfigError(ValueError):
    """A config file that this tool cannot load."""


def _encode(value: object) -> object:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _encode(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_encode(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_encode(v) for v in value)  # type: ignore[type-var]
    if isinstance(value, dict):
        return {str(k): _encode(v) for k, v in value.items()}
    return value


def _decode_untyped(value: object) -> object:
    if isinstance(value, list):
        return tuple(_decode_untyped(v) for v in value)
    if isinstance(value, dict):
        return {k: _decode_untyped(v) for k, v in value.items()}
    return value


def _decode_dataclass(cls: type, values: dict[str, object]) -> Any:
    hints = typing.get_type_hints(cls)
    known = {f.name for f in dataclasses.fields(cls)}
    return cls(**{name: _decode(value, hints[name]) for name, value in values.items() if name in known})


def _decode(value: object, hint: Any) -> Any:
    if value is None:
        return None
    origin = typing.get_origin(hint)
    args = typing.get_args(hint)
    if hint is object or hint is Any:
        return _decode_untyped(value)
    if origin in (typing.Union, types.UnionType):
        return _decode(value, next(a for a in args if a is not type(None)))
    if origin is typing.Literal:
        return value
    if dataclasses.is_dataclass(hint):
        return _decode_dataclass(hint, value)  # type: ignore[arg-type]
    if hint is Path:
        return Path(value)  # type: ignore[arg-type]
    if hint in (int, float, str, bool):
        return hint(value)
    if origin is list:
        return [_decode(v, args[0]) for v in value]  # type: ignore[attr-defined]
    if origin is set:
        return {_decode(v, args[0]) for v in value}  # type: ignore[attr-defined]
    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode(v, args[0]) for v in value)  # type: ignore[attr-defined]
        return tuple(_decode(v, a) for v, a in zip(value, args, strict=True))  # type: ignore[call-overload]
    if origin is dict:
        return {_decode(k, args[0]): _decode(v, args[1]) for k, v in value.items()}  # type: ignore[attr-defined]
    raise TypeError(f"config files have no conversion for {hint!r}")


def write_config(path: Path, tool: str, state: object, runtime_fields: frozenset[str]) -> None:
    """Writes `state`, without its `runtime_fields`, to `path` as `tool`'s config."""
    encoded = _encode(state)
    assert isinstance(encoded, dict)
    document = {
        "tool": tool,
        "format_version": FORMAT_VERSION,
        "state": {name: value for name, value in encoded.items() if name not in runtime_fields},
    }
    path.write_text(json.dumps(document, indent=2) + "\n")


def read_config(path: Path, tool: str, state_class: type, runtime_fields: frozenset[str]) -> Any:
    """A fresh `state_class` filled from the `tool` config at `path`."""
    document = json.loads(path.read_text())
    found_tool = document.get("tool") if isinstance(document, dict) else None
    if found_tool != tool:
        raise ConfigError(
            f"This is not a {tool.upper()} config"
            + (f": it was saved by {str(found_tool).upper()}." if found_tool else ".")
        )
    values = {name: value for name, value in document["state"].items() if name not in runtime_fields}
    return _decode_dataclass(state_class, values)
