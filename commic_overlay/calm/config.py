"""The CALM wizard's config file: every setting of every step, as JSON (`config_file.py`)."""

from __future__ import annotations

from pathlib import Path

from ..config_file import read_config, write_config
from .state import WizardState

TOOL = "calm"
RUN_CONFIG_FILENAME = "calm_config.json"  # written into the working directory on every Run
# The run id and the plots rendered for it belong to one run.
RUNTIME_FIELDS = frozenset({"run_id", "rendered_plots"})


def save_config(state: WizardState, path: Path) -> None:
    write_config(path, TOOL, state, RUNTIME_FIELDS)


def load_config(path: Path) -> WizardState:
    return read_config(path, TOOL, WizardState, RUNTIME_FIELDS)


def run_config_path(working_directory: Path) -> Path:
    return Path(working_directory) / RUN_CONFIG_FILENAME
