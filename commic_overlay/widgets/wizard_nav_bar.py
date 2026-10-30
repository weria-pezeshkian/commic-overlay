"""WizardNavBar: a persistent Home button, plus a dynamic, per-tool second row of steps."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

_STYLE = """
QPushButton {
    padding: 6px 12px;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 0;
    color: #8a8a8a;
    background: transparent;
    font-size: 13px;
}
QPushButton:enabled {
    color: #202020;
}
QPushButton:enabled:hover {
    color: #2a6fdb;
}
QPushButton:checked {
    font-weight: 600;
    border-bottom: 2px solid #2a6fdb;
    background: transparent;
}
"""


@dataclass(frozen=True)
class NavStep:
    key: str
    label: str
    visible_by_default: bool = True


class WizardNavBar(QWidget):
    """Top line: a persistent Home button, always enabled - takes the user all the way
    back to tool selection, regardless of which tool (if any) is currently active.

    Second line: the CURRENT tool's own step sequence, set via `set_tool_steps` - a
    different tool shows a different sequence here, which is why this is populated
    dynamically rather than being one fixed list built once. Empty/hidden until a tool
    is chosen.

    Every step entry starts locked (grayed out, unclickable) except the first, which
    starts unlocked as soon as the row is populated. `unlock(key)` permanently enables
    an entry - called once, the first time that step's page is actually shown.
    `set_current(key)` highlights which entry corresponds to the page currently on
    screen (or `set_current_home()` for the Home page itself). A step can start hidden
    (the conditional Lipid Species step) and be revealed later with `show_step(key)`
    only once its branch is actually taken.

    `step_clicked(key)` fires only for an already-unlocked, visible entry - a locked or
    hidden one simply isn't clickable in the first place. `home_clicked()` fires for the
    persistent Home button, always (the caller decides whether that needs confirming).
    """

    home_clicked = Signal()
    step_clicked = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(_STYLE)
        self._buttons: dict[str, QPushButton] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(8, 4, 8, 4)
        top_row.setSpacing(4)
        self._home_button = QPushButton("Home")
        self._home_button.setFlat(True)
        self._home_button.setCheckable(True)
        self._home_button.setChecked(True)
        self._home_button.clicked.connect(self.home_clicked)
        top_row.addWidget(self._home_button)
        top_row.addStretch(1)
        outer.addLayout(top_row)

        self._steps_container = QWidget()
        self._steps_row = QHBoxLayout(self._steps_container)
        self._steps_row.setContentsMargins(8, 0, 8, 4)
        self._steps_row.setSpacing(4)
        self._steps_container.setVisible(False)
        outer.addWidget(self._steps_container)

    def set_tool_steps(self, steps: list[NavStep]) -> None:
        """Replaces the second row with `steps` - call once, right when a tool is chosen."""
        while self._steps_row.count():
            item = self._steps_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._buttons = {}

        for i, step in enumerate(steps):
            button = QPushButton(step.label, self._steps_container)
            button.setFlat(True)
            button.setCheckable(True)
            button.setEnabled(i == 0)
            button.setVisible(step.visible_by_default)
            button.clicked.connect(lambda _checked, key=step.key: self.step_clicked.emit(key))
            self._steps_row.addWidget(button)
            self._buttons[step.key] = button

        self._steps_row.addStretch(1)
        self._steps_container.setVisible(bool(steps))

    def clear_tool_steps(self) -> None:
        self.set_tool_steps([])

    def unlock(self, key: str) -> None:
        if key in self._buttons:
            self._buttons[key].setEnabled(True)

    def show_step(self, key: str) -> None:
        if key in self._buttons:
            self._buttons[key].setVisible(True)

    def hide_step(self, key: str) -> None:
        if key in self._buttons:
            self._buttons[key].setVisible(False)

    def set_current(self, key: str) -> None:
        self._home_button.setChecked(False)
        for step_key, button in self._buttons.items():
            button.setChecked(step_key == key)

    def set_current_home(self) -> None:
        self._home_button.setChecked(True)
        for button in self._buttons.values():
            button.setChecked(False)
