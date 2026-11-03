"""Where the overlay was started from."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TextIO


def launch_directory(streams: Sequence[TextIO | None]) -> Path | None:
    """The current directory when any of `streams` is a terminal, as when a shell starts
    the overlay; None when none is, as when a desktop launcher starts it."""
    if any(stream is not None and stream.isatty() for stream in streams):
        return Path.cwd()
    return None
