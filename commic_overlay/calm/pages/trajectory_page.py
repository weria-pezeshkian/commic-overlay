"""TrajectoryPage: pick the trajectory file, plus the optional stride."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...theme import mark_primary
from ...widgets.scroll_spinbox import StrideSpinBox
from ..state import WizardState


class TrajectoryPage(QWidget):
    continue_requested = Signal()

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 32, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Please select your trajectory")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        path_row = QHBoxLayout()
        self._path_label = QLabel("No file selected.")
        self._path_label.setStyleSheet("color: #555;")
        self._path_label.setWordWrap(True)
        path_row.addWidget(self._path_label, stretch=1)
        load_button = QPushButton("Load")
        load_button.clicked.connect(self._on_load)
        path_row.addWidget(load_button)
        layout.addLayout(path_row)

        stride_row = QHBoxLayout()
        stride_row.addWidget(QLabel("Stride (optional):"))
        self._stride_spin = StrideSpinBox()
        self._stride_spin.valueChanged.connect(self._on_stride_changed)
        stride_row.addWidget(self._stride_spin)
        stride_row.addStretch(1)
        layout.addLayout(stride_row)

        layout.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self._continue_button = QPushButton("Continue")
        mark_primary(self._continue_button)
        self._continue_button.setEnabled(False)
        self._continue_button.clicked.connect(self.continue_requested)
        buttons.addWidget(self._continue_button)
        layout.addLayout(buttons)

    def refresh(self) -> None:
        """Re-displays self._state's current trajectory path and stride - call each time
        this page is shown, so an edit made elsewhere (the Advanced window) shows up here
        too, not just a path/stride picked through this page's own widgets."""
        self._show_path(self._state.trajectory_path)
        self._stride_spin.blockSignals(True)  # avoid a redundant, no-op write-back to state
        self._stride_spin.setValue(self._state.stride)
        self._stride_spin.blockSignals(False)

    def _on_load(self) -> None:
        start_dir = str(self._state.working_directory)
        path, _ = QFileDialog.getOpenFileName(
            self, "Select trajectory file", start_dir, "Trajectory files (*.xtc *.dcd);;All files (*)"
        )
        if path:
            self._state.trajectory_path = path
            self._show_path(path)

    def _show_path(self, path: str | None) -> None:
        self._path_label.setText(path or "No file selected.")
        self._continue_button.setEnabled(bool(path))

    def _on_stride_changed(self, value: int) -> None:
        self._state.stride = value
