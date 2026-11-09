"""File pickers for saving and loading a wizard's config file (`config_file.py`)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget

_FILTER = "Config files (*.json);;All files (*)"
_SUFFIX = ".json"


def suggested_config_name(tool: str) -> str:
    return f"{tool}_config_{datetime.now():%Y%m%d_%H%M}{_SUFFIX}"


def ask_config_save_path(parent: QWidget, directory: Path, tool: str) -> Path | None:
    """The path the user picks to save a config to, with `.json` added when the name has no
    suffix; None when they cancel."""
    chosen, _ = QFileDialog.getSaveFileName(
        parent, "Save config", str(Path(directory) / suggested_config_name(tool)), _FILTER
    )
    if not chosen:
        return None
    path = Path(chosen)
    return path if path.suffix else path.with_suffix(_SUFFIX)


def ask_config_load_path(parent: QWidget, directory: Path) -> Path | None:
    chosen, _ = QFileDialog.getOpenFileName(parent, "Load config", str(directory), _FILTER)
    return Path(chosen) if chosen else None
