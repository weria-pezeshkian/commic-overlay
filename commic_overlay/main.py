"""Entry point: launches the COMMIC Overlay application.

This app always opens, even if no tool it can drive is actually installed
- each tool's own Home-page button disables itself (with an explanatory
tooltip) rather than the whole app refusing to start. See
`calm/availability.py` for CALM's own check.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .launch import launch_directory
from .theme import apply_theme


def main() -> None:
    directory = launch_directory((sys.stdin, sys.stdout, sys.stderr))
    app = QApplication(sys.argv)
    apply_theme(app)

    from .app import MainWindow

    window = MainWindow(launch_directory=directory)
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
