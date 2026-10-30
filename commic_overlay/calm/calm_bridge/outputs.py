"""Where CALM's own output lands, and the exact filenames the Results page reads directly.

The two subdirectory names (`CALM_full`/`CALM_lipids`) are this overlay's
own convention, not something CALM itself names for a caller - `-o/--out`
is just a directory CALM writes whatever was asked of it into. The two
CSV filenames, by contrast, really are fixed by CALM itself
(`CALM/analyze/lipids.py::_write_area_per_lipid_csv`/
`_write_curvature_preference_csv`). Keeping all four in one place means
nothing else hardcodes them ad hoc.
"""

from __future__ import annotations

from pathlib import Path

FULL_OUTPUT_DIRNAME = "CALM_full"
LIPIDS_OUTPUT_DIRNAME = "CALM_lipids"

AREA_PER_LIPID_CSV = "area_per_lipid.csv"
CURVATURE_PREFERENCE_CSV = "curvature_preference.csv"

# CALM analyze full's own --method choices this Results page offers a plot
# button for. CALM's own METHODS tuple (CALM/analyze/full.py) also
# includes "Z_fitted" and "principal_directions", neither of which has a
# direct 'CALM map plot' --mode of its own (see CALM/map/plot.py's own
# --mode choices) - they're still always fit (this overlay's Run never
# restricts --method, so all six are always written), just not offered as
# a one-click plot button here.
PLOT_MODES = ("mean", "gaussian", "principal", "thickness")


def full_output_dir(working_dir: Path) -> Path:
    return working_dir / FULL_OUTPUT_DIRNAME


def lipids_output_dir(working_dir: Path) -> Path:
    return working_dir / LIPIDS_OUTPUT_DIRNAME


def output_dir_would_be_overwritten(path: Path) -> bool:
    """True if `path` already exists and already holds something (not just an empty directory)."""
    return path.exists() and any(path.iterdir())
