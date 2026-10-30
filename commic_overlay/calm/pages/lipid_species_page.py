"""LipidSpeciesPage: pick which resnames count as lipid species - only reached if 'lipids' was checked.

Resnames are split into two groups (`calm_bridge.validation.classify_resnames`):
a resname that only ever appears in a single-resname bonded fragment
(the shape a real lipid, water, or ion molecule has) is a genuine
lipid-species candidate and shown directly; a resname that appears in a
multi-resname fragment (the shape a protein chain has - many different
amino-acid residues all bonded into one fragment) is kept out of the main
list, collapsed into a "Show all" section instead, so a protein's two
dozen amino-acid resnames don't bury the real lipid species among them.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from ...theme import mark_primary
from ...widgets.collapsible_section import CollapsibleSection
from ..calm_bridge.validation import classify_resnames
from ..state import WizardState


class LipidSpeciesPage(QWidget):
    continue_requested = Signal()

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._checkboxes: dict[str, QCheckBox] = {}
        self._loaded_for: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Select the lipid species to include")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setSpacing(4)
        self._list_layout.setContentsMargins(0, 0, 0, 0)

        self._extra_container = QWidget()
        self._extra_layout = QVBoxLayout(self._extra_container)
        self._extra_layout.setSpacing(4)
        self._extra_layout.setContentsMargins(0, 0, 0, 0)
        self._extra_section = CollapsibleSection(self._extra_container, closed_text="Show all")

        scroll_content = QWidget()
        scroll_content_layout = QVBoxLayout(scroll_content)
        scroll_content_layout.setContentsMargins(0, 0, 0, 0)
        scroll_content_layout.addWidget(self._list_container)
        scroll_content_layout.addWidget(self._extra_section)
        scroll_content_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, stretch=1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._continue_button = QPushButton("Continue")
        mark_primary(self._continue_button)
        self._continue_button.setEnabled(False)
        self._continue_button.clicked.connect(self._on_continue)
        buttons.addWidget(self._continue_button)
        layout.addLayout(buttons)

    def refresh(self) -> None:
        """Re-lists resnames whenever a different structure is now in play, and always
        re-syncs which ones are ticked from self._state.lipid_species - call each time
        this page is shown, so an edit made elsewhere (the Advanced window) shows up here
        too, not just species ticked through this page's own checkboxes."""
        structure = self._state.structure_path
        if structure is not None and structure != self._loaded_for:
            self._loaded_for = structure
            for checkbox in self._checkboxes.values():
                checkbox.deleteLater()
            self._checkboxes.clear()

            simple, complex_ = classify_resnames(structure)

            for resname in simple:
                self._add_checkbox(resname, self._list_layout)

            for resname in complex_:
                self._add_checkbox(resname, self._extra_layout)

            self._extra_section.setVisible(bool(complex_))
            self._extra_section.set_closed_text(f"Show all ({len(complex_)} more)")

        selected = set(self._state.lipid_species)
        for resname, checkbox in self._checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(resname in selected)
            checkbox.blockSignals(False)

        self._on_changed()

    def _add_checkbox(self, resname: str, layout: QVBoxLayout) -> None:
        checkbox = QCheckBox(resname)
        checkbox.stateChanged.connect(self._on_changed)
        layout.addWidget(checkbox)
        self._checkboxes[resname] = checkbox

    def _on_changed(self) -> None:
        self._continue_button.setEnabled(any(cb.isChecked() for cb in self._checkboxes.values()))

    def _on_continue(self) -> None:
        self._state.lipid_species = [name for name, cb in self._checkboxes.items() if cb.isChecked()]
        self.continue_requested.emit()
