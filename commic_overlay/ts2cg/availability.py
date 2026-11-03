"""Whether TS2CG, and its optional mesh converters, are actually usable in this environment.

Checked up front by the Home page (the main TS2CG check) and by the mesh
file page (the two converter checks, each gating one file extension
independently) - same "discover this before a wizard page or a failed
subprocess, not during one" discipline as calm/availability.py.
"""

from __future__ import annotations

import shutil


def ts2cg_unavailable_reason() -> str | None:
    """None if TS2CG is usable; an explanatory message otherwise."""
    if shutil.which("TS2CG") is None:
        return (
            "The 'TS2CG' command was not found on PATH. Install TS2CG in this same "
            "Python environment, then relaunch COMMIC Overlay."
        )
    try:
        import TS2CG  # noqa: F401
    except ImportError as exc:
        return (
            f"The 'TS2CG' command is on PATH, but TS2CG's own Python package could not "
            f"be imported ({exc}). COMMIC Overlay needs to run in the same Python "
            "environment TS2CG is installed in."
        )
    return None


def vtk_converter_available() -> bool:
    """True if TS2CG's own .vtk/.vtu mesh converter can run (needs the optional `vtk` package)."""
    try:
        import vtk  # noqa: F401
    except ImportError:
        return False
    return True


def blender_converter_available() -> bool:
    """True if TS2CG's own .blend mesh converter can run (needs a `blender` executable on PATH)."""
    return shutil.which("blender") is not None
