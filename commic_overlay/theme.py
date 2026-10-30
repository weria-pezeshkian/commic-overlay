"""App-wide visual theme: a clean white palette, modern button styling, and a drop-shadow
helper so a page's own content panel (and a dialog's) reads as an elevated card against the
window's light-gray canvas, rather than flush, flat gray-on-gray."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QPushButton, QWidget

_STYLESHEET = """
QWidget {
    background-color: #ffffff;
    color: #1a1a1a;
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #f3f4f6;
}
QPushButton {
    background-color: #ffffff;
    border: 1px solid #d7d9dd;
    border-radius: 6px;
    padding: 6px 16px;
}
QPushButton:hover {
    border-color: #2a6fdb;
    color: #2a6fdb;
}
QPushButton:pressed {
    background-color: #eef3fc;
}
QPushButton:disabled {
    color: #aaaaaa;
    border-color: #e4e4e4;
    background-color: #f7f7f7;
}
QPushButton:checked {
    background-color: #eef3fc;
    border-color: #2a6fdb;
    color: #2a6fdb;
}
QLineEdit, QPlainTextEdit, QSpinBox, QComboBox {
    border: 1px solid #d7d9dd;
    border-radius: 4px;
    padding: 4px 6px;
    background-color: #ffffff;
    selection-background-color: #2a6fdb;
}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #2a6fdb;
}
QTableWidget {
    border: 1px solid #e4e4e4;
    gridline-color: #eeeeee;
}
QHeaderView::section {
    background-color: #fafafa;
    border: none;
    border-bottom: 1px solid #e4e4e4;
    padding: 4px;
}
QGroupBox {
    border: 1px solid #e4e4e4;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: #555555;
}
QScrollArea {
    border: none;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #c3c6cb;
    border-radius: 3px;
    background: #ffffff;
}
QCheckBox::indicator:checked {
    background: #2a6fdb;
    border-color: #2a6fdb;
}
QPushButton#primaryButton {
    background-color: #2a6fdb;
    color: #ffffff;
    border: 1px solid #2a6fdb;
    border-radius: 6px;
    font-weight: 600;
    font-size: 14px;
    padding: 10px 28px;
}
QPushButton#primaryButton:hover {
    background-color: #1f5bc4;
    border-color: #1f5bc4;
    color: #ffffff;
}
QPushButton#primaryButton:pressed {
    background-color: #184a9e;
}
QPushButton#primaryButton:disabled {
    background-color: #cdd7e8;
    border-color: #cdd7e8;
    color: #ffffff;
}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyleSheet(_STYLESHEET)


def mark_primary(button: QPushButton) -> None:
    """Marks a QPushButton as this page's single dominant action (its own Continue, Run, ...) -
    bigger, filled, and colored, so it visually outweighs secondary buttons (Change, Load,
    Advanced, Cancel) next to it. Just sets an object name the stylesheet above already
    has a #primaryButton rule for - call it once, right after constructing the button."""
    button.setObjectName("primaryButton")


def apply_drop_shadow(widget: QWidget, blur_radius: int = 28, y_offset: int = 4, alpha: int = 45) -> None:
    """Gives `widget` a soft drop shadow, so it reads as an elevated panel rather than
    flush with the window's own background behind it.

    `widget` needs its own solid background and some margin around it in its
    parent layout for the blur to actually render rather than being clipped.
    """
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur_radius)
    effect.setOffset(0, y_offset)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)
