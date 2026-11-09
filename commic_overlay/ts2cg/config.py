"""The TS2CG wizard's config file: every setting of every step, as JSON (`config_file.py`)."""

from __future__ import annotations

from pathlib import Path

from ..config_file import read_config, write_config
from .state import WizardState

TOOL = "ts2cg"
RUN_CONFIG_FILENAME = "ts2cg_config.json"  # written into the working directory on every Run
# The preview directory and the run id belong to one session. `preview_signature` stays: it
# records the settings the Place Domains points were picked on.
RUNTIME_FIELDS = frozenset({"preview_point_dir", "run_id"})


def save_config(state: WizardState, path: Path) -> None:
    write_config(path, TOOL, state, RUNTIME_FIELDS)


def load_config(path: Path) -> WizardState:
    return read_config(path, TOOL, WizardState, RUNTIME_FIELDS)


def run_config_path(working_directory: Path) -> Path:
    return Path(working_directory) / RUN_CONFIG_FILENAME
