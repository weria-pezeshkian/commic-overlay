"""HomePage: the landing page - picks which tool to drive."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from ..calm.availability import calm_unavailable_reason


class HomePage(QWidget):
    """"Welcome to the COMMIC Overlay, which task would you like to perform" + one button per tool.

    Only `CALM` exists for now; a sibling tool gets its own button here
    later, emitting its own key. A tool's button disables itself (with an
    explanatory tooltip) rather than the whole app refusing to start when
    that tool isn't actually installed - so this page only ever offers
    what's really usable right now.
    """

    tool_selected = Signal(str)  # tool key, e.g. "calm"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(24)

        title = QLabel("Welcome to the COMMIC Overlay")
        title.setStyleSheet("font-size: 22px; font-weight: 600;")
        layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignHCenter)

        subtitle = QLabel("Which task would you like to perform?")
        subtitle.setStyleSheet("font-size: 14px; color: #555;")
        layout.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._calm_button = QPushButton("CALM")
        self._calm_button.setMinimumSize(160, 48)
        self._calm_button.setStyleSheet("font-size: 16px;")
        self._calm_button.clicked.connect(lambda: self.tool_selected.emit("calm"))
        layout.addWidget(self._calm_button, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addStretch(1)

        self.refresh()

    def refresh(self) -> None:
        reason = calm_unavailable_reason()
        self._calm_button.setEnabled(reason is None)
        self._calm_button.setToolTip(reason or "")
