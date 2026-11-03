"""SelectLipidsPage: tick every lipid that should appear in the membrane, in both monolayers.

Grouped by the itp file each lipid comes from (`lipidome.py::group_label`),
collapsed by default - click a group's own name to expand it. The search
field filters across every group at once, auto-expanding any group with a
match and hiding the rest; clearing it restores the collapsed default. A
"custom" group (initially empty) holds whatever itp files were added
through the Advanced popup (`custom_itp_dialog.py`).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...theme import mark_primary
from ...widgets.collapsible_section import CollapsibleSection
from ..state import WizardState
from ..ts2cg_bridge.lipidome import LipidomeIndex, fetch_lipidome, group_label, index_lipidome, itp_dir
from .custom_itp_dialog import CustomItpDialog

CUSTOM_GROUP_LABEL = "custom"
_DEFAULT_CACHE_DIR = Path.home() / ".cache" / "commic_overlay" / "lipidome"


class SelectLipidsPage(QWidget):
    continue_requested = Signal()

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._lipidome_index: LipidomeIndex | None = None
        self._lipid_to_itp: dict[str, Path] = {}
        self._group_sections: dict[str, CollapsibleSection] = {}
        self._checkboxes: dict[str, QCheckBox] = {}
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Select all the lipids that should appear in the membrane, in both monolayers.")
        title.setWordWrap(True)
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        top_row = QHBoxLayout()
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Search lipids…")
        self._search_edit.textChanged.connect(self._on_search_changed)
        top_row.addWidget(self._search_edit, stretch=1)
        advanced_button = QPushButton("Advanced")
        advanced_button.clicked.connect(self._on_advanced_clicked)
        top_row.addWidget(advanced_button)
        layout.addLayout(top_row)

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #999; font-size: 12px;")
        layout.addWidget(self._status_label)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        layout.addWidget(self._scroll_area, stretch=1)

        self._groups_container = QWidget()
        self._groups_layout = QVBoxLayout(self._groups_container)
        self._groups_layout.setSpacing(4)
        self._groups_layout.addStretch(1)
        self._scroll_area.setWidget(self._groups_container)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        self._continue_button = QPushButton("Continue")
        mark_primary(self._continue_button)
        self._continue_button.setEnabled(False)
        self._continue_button.clicked.connect(self.continue_requested)
        buttons_row.addWidget(self._continue_button)
        layout.addLayout(buttons_row)

    def refresh(self) -> None:
        """Fetches/indexes the lipidome once (cached on first visit), rebuilds the custom
        group from state.custom_itp_paths every time (cheap, and the Advanced popup may
        have changed it since the last visit), and re-syncs checked state from
        state.selected_lipids - mirrors every other page's own refresh() contract."""
        if not self._loaded:
            self._load_lipidome()
            self._loaded = True
        self._rebuild_custom_group()
        self._sync_checked_state()
        self._update_continue_enabled()

    def _load_lipidome(self) -> None:
        self._status_label.setText("Fetching the Martini 3 lipidome…")
        cache_dir = self._state.lipidome_cache_dir or _DEFAULT_CACHE_DIR
        try:
            lipidome_dir = fetch_lipidome(cache_dir)
            self._state.lipidome_cache_dir = cache_dir
            self._lipidome_index = index_lipidome(itp_dir(lipidome_dir))
        except OSError as exc:
            self._status_label.setText(f"Could not fetch the lipidome: {exc}")
            self._lipidome_index = LipidomeIndex()

        self._lipid_to_itp = dict(self._lipidome_index.lipid_to_itp)
        for itp_path, names in sorted(self._lipidome_index.itp_to_lipids.items(), key=lambda kv: group_label(kv[0])):
            self._add_group(group_label(itp_path), names)
        self._status_label.setText("")
        self._sync_lipid_to_itp_onto_state()

    def _sync_lipid_to_itp_onto_state(self) -> None:
        """Pushes this page's own merged lipid->itp map onto state.lipid_to_itp, so the
        Run pipeline can build the .LIB file directly from it - no re-fetch, no re-index."""
        self._state.lipid_to_itp = dict(self._lipid_to_itp)

    def _add_group(self, label: str, names: list[str]) -> None:
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 4, 0, 4)
        content_layout.setSpacing(2)
        for name in names:
            checkbox = QCheckBox(name)
            checkbox.stateChanged.connect(self._on_checkbox_changed)
            content_layout.addWidget(checkbox)
            self._checkboxes[name] = checkbox

        section = CollapsibleSection(content, closed_text=f"{label} ({len(names)})", open_text=f"{label} ▾")
        self._group_sections[label] = section
        # Insert before the trailing stretch - groups_layout's last item.
        self._groups_layout.insertWidget(self._groups_layout.count() - 1, section)

    def _rebuild_custom_group(self) -> None:
        custom_map = CustomItpDialog.parse_custom_lipids(self._state.custom_itp_paths)
        # Drop any previously-indexed custom lipids before merging the fresh set, so a
        # lipid removed via the Advanced popup doesn't linger in _lipid_to_itp/_checkboxes.
        for name in list(self._lipid_to_itp):
            if self._lipidome_index is not None and name not in self._lipidome_index.lipid_to_itp:
                del self._lipid_to_itp[name]
        self._lipid_to_itp.update(custom_map)
        self._sync_lipid_to_itp_onto_state()

        existing_section = self._group_sections.pop(CUSTOM_GROUP_LABEL, None)
        if existing_section is not None:
            self._groups_layout.removeWidget(existing_section)
            existing_section.deleteLater()
            # Remove stale custom checkboxes (anything not in the lipidome index and not in
            # the freshly-parsed custom_map) from the tracked dict so they don't linger.
            for name in list(self._checkboxes.keys()):
                if self._lipidome_index is not None and name in self._lipidome_index.lipid_to_itp:
                    continue
                if name not in custom_map:
                    del self._checkboxes[name]

        if custom_map:
            self._add_group(CUSTOM_GROUP_LABEL, sorted(custom_map.keys()))

    def _sync_checked_state(self) -> None:
        selected = set(self._state.selected_lipids)
        for name, checkbox in self._checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(name in selected)
            checkbox.blockSignals(False)

    def _on_checkbox_changed(self) -> None:
        self._state.selected_lipids = [name for name, box in self._checkboxes.items() if box.isChecked()]
        self._update_continue_enabled()

    def _update_continue_enabled(self) -> None:
        self._continue_button.setEnabled(bool(self._state.selected_lipids))

    def _on_search_changed(self, text: str) -> None:
        query = text.strip().lower()
        if not query:
            for section in self._group_sections.values():
                section.set_expanded(False)
                section.setVisible(True)
            for checkbox in self._checkboxes.values():
                checkbox.setVisible(True)
            return

        # Map each checkbox's own lipid name back to the group section that contains it,
        # so a match in one group doesn't force-expand an unrelated one.
        name_to_group: dict[str, str] = {}
        for group_label_, section in self._group_sections.items():
            for checkbox in section.content.findChildren(QCheckBox):
                name_to_group[checkbox.text()] = group_label_

        matches_by_group: dict[str, bool] = dict.fromkeys(self._group_sections, False)
        for name, checkbox in self._checkboxes.items():
            matches = query in name.lower()
            checkbox.setVisible(matches)
            group = name_to_group.get(name)
            if matches and group is not None:
                matches_by_group[group] = True

        for label, section in self._group_sections.items():
            has_match = matches_by_group.get(label, False)
            section.setVisible(has_match)
            section.set_expanded(has_match)

    def _on_advanced_clicked(self) -> None:
        dialog = CustomItpDialog(self._state, self)
        dialog.exec()
        self._rebuild_custom_group()
        self._sync_checked_state()
