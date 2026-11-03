"""DomainCountPage: how many lipid domains the membrane should have (default 1, Domain 0
always exists - increasing this adds Domain 1, Domain 2, ..., which Distribute Domains and
Place Domains give points and Sort Lipids gives a composition)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...theme import mark_primary
from ...widgets.scroll_spinbox import StrideSpinBox
from ..state import WizardState


class DomainCountPage(QWidget):
    continue_requested = Signal()

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Number of domains")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        description = QLabel(
            "How many separate lipid domains should the membrane have? Domain 0 always "
            "exists - increase this only if you want additional, separately-composed regions. "
            "You can continue without changing anything."
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #555;")
        layout.addWidget(description)

        count_row = QHBoxLayout()
        count_row.addWidget(QLabel("Domains:"))
        self._count_box = StrideSpinBox()
        self._count_box.valueChanged.connect(self._on_count_changed)
        count_row.addWidget(self._count_box)
        count_row.addStretch(1)
        layout.addLayout(count_row)

        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._continue_button = QPushButton("Continue")
        mark_primary(self._continue_button)
        self._continue_button.clicked.connect(self.continue_requested)
        buttons.addWidget(self._continue_button)
        layout.addLayout(buttons)

    def refresh(self) -> None:
        self._count_box.blockSignals(True)
        self._count_box.setValue(self._state.domain_count)
        self._count_box.blockSignals(False)

    def _on_count_changed(self, value: int) -> None:
        self._state.domain_count = value
