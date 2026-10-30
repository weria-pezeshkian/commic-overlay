"""Opening a finished result file in whatever the OS's own default application for it is."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, QUrl
from PySide6.QtGui import QDesktopServices


def open_in_default_app(path: Path) -> None:
    """Opens `path` in the OS's own default application - no interactive chooser.

    On Linux, `QDesktopServices.openUrl` goes through the desktop's own
    "open URI" portal when one is active, which (unlike a plain
    `xdg-open`) asks the user to pick an application on every single
    call instead of remembering a default - confirmed against this
    environment's own behavior. `xdg-open` itself reads the user's real
    `mimeapps.list` default directly and opens silently, so it's tried
    first when present; `QDesktopServices` is the fallback, covering
    every other platform (and a Linux system with no `xdg-open` at all),
    where it already opens the real system default with no such prompt.
    """
    if sys.platform.startswith("linux") and shutil.which("xdg-open"):
        if QProcess.startDetached("xdg-open", [str(path)]):
            return
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
