"""Whether CALM is actually usable in this environment.

Checked once, up front - by the Home page, to decide whether its CALM
button should even be clickable - rather than discovered deep inside a
wizard page or a failed subprocess launch. A sibling tool would get its
own equivalent check, used the same way.
"""

from __future__ import annotations

import shutil


def calm_unavailable_reason() -> str | None:
    """None if CALM is usable; an explanatory message otherwise."""
    if shutil.which("CALM") is None:
        return (
            "The 'CALM' command was not found on PATH. Install CALM in this same "
            "Python environment, then relaunch COMMIC Overlay."
        )
    try:
        import CALM  # noqa: F401
    except ImportError as exc:
        return (
            f"The 'CALM' command is on PATH, but CALM's own Python package could not "
            f"be imported ({exc}). COMMIC Overlay needs to run in the same Python "
            "environment CALM is installed in."
        )
    return None
