"""Persisted, per-user settings - currently just the last-used working directory.

Backed by `QSettings` (Qt's own cross-platform settings store - an INI
file under the user's config dir on Linux, the registry on Windows, a
plist on macOS), not a hand-rolled JSON file: it's the standard mechanism
for exactly this kind of small, per-user state, and needs no path-handling
of our own. Nothing here is shared across tools yet, but it isn't
CALM-specific either - a sibling tool reuses the same working-directory
concept, so this stays at the top level alongside `app.py`.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

_ORG = "COMMIC"
_APP = "Overlay"
_WORKING_DIR_KEY = "working_directory"


def _settings() -> QSettings:
    return QSettings(_ORG, _APP)


def get_last_working_directory() -> Path | None:
    """The remembered working directory, or None if there isn't one (first run, or it no longer exists)."""
    value = _settings().value(_WORKING_DIR_KEY, None)
    if not value:
        return None
    path = Path(value)
    return path if path.is_dir() else None


def set_last_working_directory(path: Path) -> None:
    _settings().setValue(_WORKING_DIR_KEY, str(path))
