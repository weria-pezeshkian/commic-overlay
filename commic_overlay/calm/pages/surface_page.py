"""SurfacePage: the leaflet-detection selection string (-n), validated against the structure."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ...theme import mark_primary
from ..calm_bridge.validation import validate_selection
from ..state import WizardState


class SurfacePage(QWidget):
    continue_requested = Signal()

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Please select what represents your surface")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        # Placeholder for an illustrative image, supplied later.
        self._image_placeholder = QLabel("[image placeholder]")
        self._image_placeholder.setFixedHeight(120)
        self._image_placeholder.setStyleSheet("border: 1px dashed #bbb; color: #999; background: #fafafa;")
        self._image_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._image_placeholder)

        self._selection_edit = QLineEdit()
        self._selection_edit.setPlaceholderText("e.g. name PO4")
        self._selection_edit.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._selection_edit)

        self._message_label = QLabel("")
        self._message_label.setWordWrap(True)
        layout.addWidget(self._message_label)

        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._continue_button = QPushButton("Continue")
        mark_primary(self._continue_button)
        self._continue_button.setEnabled(False)
        self._continue_button.clicked.connect(self._on_continue)
        buttons.addWidget(self._continue_button)
        layout.addLayout(buttons)

    def refresh(self) -> None:
        """Re-displays self._state.surface_selection - call each time this page is shown,
        so an edit made elsewhere (the Advanced window) shows up here too, not just a
        selection typed through this page's own text box."""
        self._selection_edit.setText(self._state.surface_selection)

    def _on_text_changed(self, text: str) -> None:
        self._continue_button.setEnabled(bool(text.strip()))
        self._message_label.setText("")
        self._message_label.setStyleSheet("")

    def _on_continue(self) -> None:
        text = self._selection_edit.text().strip()
        if not text or not self._state.structure_path:
            return
        result = validate_selection(self._state.structure_path, text)
        if not result.ok:
            self._message_label.setText(result.message)
            self._message_label.setStyleSheet("color: #b00020;")
            return
        self._state.surface_selection = text
        self._message_label.setText(result.message)
        self._message_label.setStyleSheet("color: #2a6fdb;")
        self.continue_requested.emit()
