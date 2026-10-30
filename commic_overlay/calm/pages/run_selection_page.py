"""RunSelectionPage: choose which CALM commands to run (full, lipids)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from ...theme import mark_primary
from ..calm_bridge.validation import has_bond_information
from ..state import WizardState

_NO_BONDS_MESSAGE = (
    "For lipids one needs a .tpr — the structure you supplied doesn't appear to carry "
    "bonded information. Please go back to Structure and select an appropriate file."
)


class RunSelectionPage(QWidget):
    continue_requested = Signal()

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        # True once Continue has actually succeeded here once - see
        # _on_changed/_on_continue's own docstrings for why this changes
        # how (and when) the structure's bond information gets checked.
        self._confirmed_once = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Select what you want to run")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        self._full_check = QCheckBox("full — geometric analysis (thickness, curvature)")
        self._full_check.stateChanged.connect(self._on_changed)
        layout.addWidget(self._full_check)

        self._lipids_check = QCheckBox("lipids — per-species area and curvature preference")
        self._lipids_check.stateChanged.connect(self._on_lipids_changed)
        layout.addWidget(self._lipids_check)

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
        # Re-sync the checkboxes from state first (signals blocked - this
        # is a display refresh, not a user edit, so it must never pop the
        # no-bonds warning on its own), then re-evaluate Continue's own
        # gating unconditionally - e.g. after going back to Structure and
        # picking a .tpr, Continue must re-enable on its own, without the
        # user re-ticking the checkbox.
        self._full_check.blockSignals(True)
        self._lipids_check.blockSignals(True)
        self._full_check.setChecked(self._state.run_full)
        self._lipids_check.setChecked(self._state.run_lipids)
        self._full_check.blockSignals(False)
        self._lipids_check.blockSignals(False)
        self._on_changed()

    def _on_lipids_changed(self) -> None:
        # has_bond_information() loads the whole structure through
        # MDAnalysis - too slow to run on every single tick (it made
        # ticking the box itself feel laggy, as if the click were doing
        # real work). The first time through this page, ticking just
        # updates Continue's own enabled state cheaply; the real check -
        # and its warning popup if it fails - happens once, when Continue
        # is actually clicked (_on_continue). Once this page has been
        # confirmed once (its own next steps are no longer grayed out),
        # the live per-tick check comes back, same as before.
        if self._confirmed_once and self._lipids_check.isChecked() and not self._lipids_prereq_ok():
            QMessageBox.warning(self, "Structure missing bond information", _NO_BONDS_MESSAGE)
        self._on_changed()

    def _lipids_prereq_ok(self) -> bool:
        if not self._lipids_check.isChecked():
            return True
        if not self._state.structure_path:
            return False
        return has_bond_information(self._state.structure_path)

    def _on_changed(self) -> None:
        any_checked = self._full_check.isChecked() or self._lipids_check.isChecked()
        if self._confirmed_once:
            self._continue_button.setEnabled(any_checked and self._lipids_prereq_ok())
        else:
            # First time through: stay responsive - the (possibly slow)
            # bond check runs once, in _on_continue, not on every tick.
            self._continue_button.setEnabled(any_checked)

    def _on_continue(self) -> None:
        if self._lipids_check.isChecked() and not self._lipids_prereq_ok():
            QMessageBox.warning(self, "Structure missing bond information", _NO_BONDS_MESSAGE)
            self._continue_button.setEnabled(False)
            return
        self._state.run_full = self._full_check.isChecked()
        self._state.run_lipids = self._lipids_check.isChecked()
        self._confirmed_once = True
        self.continue_requested.emit()
