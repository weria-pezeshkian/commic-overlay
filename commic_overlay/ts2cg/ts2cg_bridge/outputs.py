"""Where TS2CG's own output lands, and the overlay's own fixed-file convention.

`TS2CG_point/` holds the point directory `PLM` (mesh-file path) or
`PCG -WPointDir` (analytical-shape path) builds, and whatever `INU` calls
then add inclusions into. `TS2CG_build/` holds the final `PCG -function
backmap` output (`.gro`/`.top`/`pcg.log`), plus the `input.str` this
overlay wrote and the `.LIB` it assembled for that build - mirrors
calm/calm_bridge/outputs.py's own fixed-subdirectory convention, so
nothing else hardcodes these names ad hoc.
"""

from __future__ import annotations

from pathlib import Path

POINT_DIRNAME = "TS2CG_point"
BUILD_DIRNAME = "TS2CG_build"

INPUT_STR_FILENAME = "input.str"
LIB_FILENAME = "Martini3.LIB"
OUTPUT_PREFIX = "membrane"  # PCG's own -defout - produces membrane.gro / membrane.top


def point_dir(working_dir: Path) -> Path:
    return working_dir / POINT_DIRNAME


def build_dir(working_dir: Path) -> Path:
    return working_dir / BUILD_DIRNAME


def output_dir_would_be_overwritten(path: Path) -> bool:
    """True if `path` already exists and already holds something (not just an empty directory)."""
    return path.exists() and any(path.iterdir())
