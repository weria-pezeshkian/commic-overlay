"""ResultsPage: one-click plots for whatever was run, plus the lipid CSV tables."""

from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...open_file import open_in_default_app
from ..calm_bridge import outputs
from ..calm_bridge.runner import CommandRunner
from ..state import WizardState


class ResultsPage(QWidget):
    """Buttons for whichever subset of mean/gaussian/principal/thickness (if `full` ran) and
    `lipids` (if `lipids` ran) apply. Clicking one opens that plot's image in the OS's own
    default viewer - rendering it with the matching `CALM map ...` command first only if it
    hasn't already been rendered for the CURRENT run. Each rendered file is named with the
    run's own `state.run_id` (stamped fresh by `app.py` each time Run starts) and recorded in
    `state.rendered_plots`, so a later click against an already-rendered mode just reopens
    that same file - no rerun - while a plot rendered by an earlier run (different run_id,
    possibly different parameters) is never mistaken for one that's still current.

    `--histogram` is always passed to `CALM map plot` (the four full-based
    buttons); `--alpha-TMD` is added to those same calls, and to `CALM map
    lipids_plot`'s own call, only if Remove-TMD was used for the run - on
    both commands it fades a Remove-TMD hole point toward white by how
    many averaged frames it was actually missing in, instead of blanking
    it outright on a single bad frame.
    """

    def __init__(self, state: WizardState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = state
        self._runner = CommandRunner(self)
        self._runner.finished.connect(self._on_plot_finished)
        self._pending_image_path: Path | None = None
        self._pending_key: str | None = None
        self._plot_buttons: list[QPushButton] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(16)

        title = QLabel("Results")
        title.setStyleSheet("font-size: 16px;")
        layout.addWidget(title)

        self._buttons_row = QHBoxLayout()
        layout.addLayout(self._buttons_row)

        status_row = QHBoxLayout()
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #555;")
        status_row.addWidget(self._status_label)
        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setVisible(False)
        self._cancel_button.clicked.connect(self._on_cancel_clicked)
        status_row.addWidget(self._cancel_button)
        status_row.addStretch(1)
        layout.addLayout(status_row)

        self._tables_container = QVBoxLayout()
        layout.addLayout(self._tables_container)
        layout.addStretch(1)

    def refresh(self) -> None:
        """Rebuilds the button row and loads lipid tables - call each time this page is shown."""
        self._clear_layout(self._buttons_row)
        self._clear_layout(self._tables_container)
        self._plot_buttons = []

        if self._state.run_full:
            for mode in outputs.PLOT_MODES:
                button = QPushButton(mode)
                button.clicked.connect(lambda _checked, m=mode: self._run_full_plot(m))
                self._buttons_row.addWidget(button)
                self._plot_buttons.append(button)

        if self._state.run_lipids:
            lipids_button = QPushButton("lipids")
            lipids_button.clicked.connect(self._run_lipids_plot)
            self._buttons_row.addWidget(lipids_button)
            self._plot_buttons.append(lipids_button)
            self._load_lipid_tables()

        self._buttons_row.addStretch(1)

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _set_buttons_enabled(self, enabled: bool) -> None:
        for button in self._plot_buttons:
            button.setEnabled(enabled)

    def _already_rendered(self, key: str) -> Path | None:
        """The path recorded for `key` under the CURRENT run_id, if that file is still there."""
        path = self._state.rendered_plots.get(key)
        if path is not None and path.exists():
            return path
        return None

    def _run_full_plot(self, mode: str) -> None:
        if self._runner.is_running():
            return
        key = f"full:{mode}"
        existing = self._already_rendered(key)
        if existing is not None:
            open_in_default_app(existing)
            return
        out_dir = outputs.full_output_dir(self._state.working_directory)
        image_path = out_dir / f"{mode}_{self._state.run_id}.png"
        argv = ["CALM", "map", "plot", "-i", str(out_dir), "--mode", mode, "-o", str(image_path), "--histogram"]
        if self._state.remove_tmd:
            argv.append("--alpha-TMD")
        self._pending_image_path = image_path
        self._pending_key = key
        self._status_label.setText(f"Rendering {mode}…")
        self._set_buttons_enabled(False)
        self._cancel_button.setVisible(True)
        self._runner.start(argv, str(out_dir))

    def _run_lipids_plot(self) -> None:
        if self._runner.is_running():
            return
        key = "lipids"
        existing = self._already_rendered(key)
        if existing is not None:
            open_in_default_app(existing)
            return
        out_dir = outputs.lipids_output_dir(self._state.working_directory)
        image_path = out_dir / f"lipids_{self._state.run_id}.png"
        argv = ["CALM", "map", "lipids_plot", "-i", str(out_dir), "-o", str(image_path)]
        if self._state.remove_tmd:
            argv.append("--alpha-TMD")
        self._pending_image_path = image_path
        self._pending_key = key
        self._status_label.setText("Rendering lipids…")
        self._set_buttons_enabled(False)
        self._cancel_button.setVisible(True)
        self._runner.start(argv, str(out_dir))

    def _on_cancel_clicked(self) -> None:
        self._status_label.setText("Cancelling…")
        self._cancel_button.setEnabled(False)
        self._runner.stop()

    def _on_plot_finished(self, exit_code: int) -> None:
        image_path = self._pending_image_path
        key = self._pending_key
        self._pending_image_path = None
        self._pending_key = None
        self._status_label.setText("")
        self._set_buttons_enabled(True)
        self._cancel_button.setVisible(False)
        self._cancel_button.setEnabled(True)
        if self._runner.was_stopped():
            return
        if exit_code != 0 or image_path is None or not image_path.exists():
            QMessageBox.critical(self, "Plot failed", "CALM map plot/lipids_plot did not produce an image.")
            return
        if key is not None:
            self._state.rendered_plots[key] = image_path
        open_in_default_app(image_path)

    def _load_lipid_tables(self) -> None:
        out_dir = outputs.lipids_output_dir(self._state.working_directory)
        self._add_csv_table("Area per lipid", out_dir / outputs.AREA_PER_LIPID_CSV)
        self._add_csv_table("Curvature preference", out_dir / outputs.CURVATURE_PREFERENCE_CSV)

    def _add_csv_table(self, title: str, csv_path: Path) -> None:
        # A container QWidget, not a bare addLayout: _clear_layout only
        # sweeps direct widget items, so a nested layout's own widgets
        # (the label, the button below) would otherwise leak on every
        # refresh() instead of being deleted along with their container.
        header = QWidget()
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(0, 0, 0, 0)
        label = QLabel(title)
        label.setStyleSheet("font-weight: 600; margin-top: 12px;")
        header_row.addWidget(label)
        header_row.addStretch(1)
        if csv_path.exists():
            view_button = QPushButton("View as CSV")
            view_button.clicked.connect(lambda _checked, p=csv_path: open_in_default_app(p))
            header_row.addWidget(view_button)
        self._tables_container.addWidget(header)

        if not csv_path.exists():
            missing = QLabel(f"({csv_path.name} not found)")
            missing.setStyleSheet("color: #999;")
            self._tables_container.addWidget(missing)
            return

        with open(csv_path, newline="") as f:
            rows = list(csv.reader(f))
        if not rows:
            return
        header, *data_rows = rows

        table = QTableWidget(len(data_rows), len(header))
        table.setHorizontalHeaderLabels(header)
        for r, row in enumerate(data_rows):
            for c, value in enumerate(row):
                table.setItem(r, c, QTableWidgetItem(value))
        table.resizeColumnsToContents()
        table.setMaximumHeight(200)
        self._tables_container.addWidget(table)
