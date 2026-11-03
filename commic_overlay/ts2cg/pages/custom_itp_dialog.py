"""CustomItpDialog: add one or more custom itp files, shown under Select Lipids' own "custom" group."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout

from ...theme import mark_primary
from ..state import WizardState


class CustomItpDialog(QDialog):
    """A small popup listing `state.custom_itp_paths`, with Add/Remove - every lipid found
    in these files is merged into the Select Lipids page's own "custom" group once this
    dialog closes (the page re-indexes `state.custom_itp_paths` itself; this dialog only
    edits the path list)."""

    def __init__(self, state: WizardState, parent=None) -> None:
        super().__init__(parent)
        self._state = state
        self.setWindowTitle("Add custom itp files")
        self.resize(480, 320)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        intro = QLabel("Lipids found in these itp files appear under \"custom\" on the Select Lipids page.")
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #555;")
        layout.addWidget(intro)

        self._list = QListWidget()
        self._list.addItems(self._state.custom_itp_paths)
        layout.addWidget(self._list, stretch=1)

        buttons_row = QHBoxLayout()
        add_button = QPushButton("Add file(s)…")
        add_button.clicked.connect(self._on_add)
        buttons_row.addWidget(add_button)
        remove_button = QPushButton("Remove selected")
        remove_button.clicked.connect(self._on_remove)
        buttons_row.addWidget(remove_button)
        buttons_row.addStretch(1)
        layout.addLayout(buttons_row)

        done_row = QHBoxLayout()
        done_row.addStretch(1)
        done_button = QPushButton("Done")
        mark_primary(done_button)
        done_button.clicked.connect(self.accept)
        done_row.addWidget(done_button)
        layout.addLayout(done_row)

    def _on_add(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select itp file(s)", "", "itp files (*.itp);;All files (*)")
        for path in paths:
            if path not in self._state.custom_itp_paths:
                self._state.custom_itp_paths.append(path)
                self._list.addItem(path)

    def _on_remove(self) -> None:
        for item in self._list.selectedItems():
            path = item.text()
            if path in self._state.custom_itp_paths:
                self._state.custom_itp_paths.remove(path)
            self._list.takeItem(self._list.row(item))

    @staticmethod
    def parse_custom_lipids(custom_itp_paths: list[str]) -> dict[str, Path]:
        """lipid name -> its own custom itp file, for every molecule found across all of them.

        Uses TS2CG's own `read_itp_molecules` directly - same parser
        `lipidome.py::index_lipidome` uses for the fetched lipidome, so a
        custom lipid behaves identically to a fetched one everywhere
        downstream (the Select Lipids page's own checklist,
        `libmaker_bridge.build_lib_file`'s `lipid_to_itp` map).
        """
        from TS2CG.core.itp_parser import read_itp_molecules

        result: dict[str, Path] = {}
        for raw_path in custom_itp_paths:
            path = Path(raw_path)
            if not path.exists():
                continue
            for mol in read_itp_molecules(path):
                result[mol.name] = path
        return result
