"""CollapsibleSection: a small, unobtrusive 'Show all' toggle that reveals/hides a content widget."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget


class CollapsibleSection(QWidget):
    """A toggle button plus a content widget, collapsed (content hidden) by default.

    The button sits in its own row with a trailing stretch, so it hugs its
    own text width (left-aligned, no bigger than it needs to be) instead
    of stretching to fill the row the way a bare `QVBoxLayout.addWidget`
    would - it's a minor, secondary affordance, not something that should
    visually compete with the page's own checkboxes above it.
    """

    def __init__(
        self,
        content: QWidget,
        closed_text: str = "Show all",
        open_text: str = "Hide",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._closed_text = closed_text
        self._open_text = open_text

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        self._toggle_button = QPushButton(closed_text)
        self._toggle_button.setFlat(True)
        self._toggle_button.setCheckable(True)
        self._toggle_button.setStyleSheet("padding: 2px 8px; font-size: 12px; color: #666;")
        self._toggle_button.toggled.connect(self._on_toggled)
        button_row.addWidget(self._toggle_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        self._content = content
        self._content.setVisible(False)
        layout.addWidget(self._content)

    def _on_toggled(self, checked: bool) -> None:
        self._content.setVisible(checked)
        self._toggle_button.setText(self._open_text if checked else self._closed_text)

    def set_closed_text(self, text: str) -> None:
        self._closed_text = text
        if not self._toggle_button.isChecked():
            self._toggle_button.setText(text)
