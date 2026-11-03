"""ResultsPage: TS2CG's own output is a final structure/topology, not plottable the way
CALM's .npy output is - this page just gives quick access to it: open the build folder,
or open the .gro directly in the OS's own default viewer."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...open_file import open_in_default_app
from ..state import WizardState
from ..ts2cg_bridge.outputs import OUTPUT_PREFIX, build_dir


class ResultsPage(QWidget):
    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Results")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("color: #555;")
        layout.addWidget(self._status_label)

        buttons_row = QHBoxLayout()
        open_folder_button = QPushButton("Open build folder")
        open_folder_button.clicked.connect(self._on_open_folder)
        buttons_row.addWidget(open_folder_button)
        self._open_gro_button = QPushButton("Open membrane.gro")
        self._open_gro_button.clicked.connect(self._on_open_gro)
        buttons_row.addWidget(self._open_gro_button)
        buttons_row.addStretch(1)
        layout.addLayout(buttons_row)

        layout.addStretch(1)

    def refresh(self) -> None:
        out_dir = build_dir(self._state.working_directory)
        gro_path = out_dir / f"{OUTPUT_PREFIX}.gro"
        top_path = out_dir / f"{OUTPUT_PREFIX}.top"
        if gro_path.exists() and top_path.exists():
            self._status_label.setText(f"Built: {gro_path.name}, {top_path.name}\n{out_dir}")
            self._open_gro_button.setEnabled(True)
        else:
            self._status_label.setText(f"No output found yet in {out_dir}")
            self._open_gro_button.setEnabled(False)

    def _on_open_folder(self) -> None:
        open_in_default_app(build_dir(self._state.working_directory))

    def _on_open_gro(self) -> None:
        open_in_default_app(build_dir(self._state.working_directory) / f"{OUTPUT_PREFIX}.gro")
