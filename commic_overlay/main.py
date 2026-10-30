"""Entry point: launches the COMMIC Overlay application.

This app always opens, even if no tool it can drive is actually installed
- each tool's own Home-page button disables itself (with an explanatory
tooltip) rather than the whole app refusing to start. See
`calm/availability.py` for CALM's own check.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .theme import apply_theme


def main() -> None:
    app = QApplication(sys.argv)
    apply_theme(app)

    from .app import MainWindow

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
