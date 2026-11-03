"""AddProteinDialog: load a protein .gro, see it live against the two leaflet planes, and
collect everything one `ProteinSpec` needs - INU's own placement fields (radius, count,
optional curvature targeting, seed) plus the `[Protein List]` entry it becomes (`Z0`, the
real depth mechanism - see `state.py::ProteinSpec`'s own docstring for why `.gro`
coordinates are never touched to express depth; `Ratio`, always collected even though this
placement path doesn't consult it at runtime - PCG's own `[Protein List]` parser requires
the line regardless).

Opened with an `existing` protein, it edits that protein: every field starts from its values,
its structure is reloaded, and the result keeps its type id.
"""

from __future__ import annotations

import matplotlib
import numpy as np

matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...theme import mark_primary
from ...widgets.float_spinbox import FloatSpinBox
from ...widgets.scroll_spinbox import IntSpinBox
from ..state import ProteinSpec, WizardState

_DEFAULT_THICKNESS = 3.8  # TS2CG PLM's own -bilayerThickness default
_DIALOG_SIZE = (1180, 700)
_SCREEN_MARGIN = 80  # kept free around the dialog when the screen is smaller than _DIALOG_SIZE
_PREVIEW_MINIMUM_SIZE = 420
_SETTINGS_MAXIMUM_WIDTH = 560
_PREVIEW_ZOOM = 0.85  # shrinks the 3D box inside the canvas so the tick labels fit


def _current_bilayer_thickness(state: WizardState) -> float:
    """Whatever membrane thickness is actually in effect for this run right now - the
    analytical shape's own Thickness field, or PLM's -bilayerThickness override if the
    mesh-file path set one, falling back to PLM's own real default otherwise. Read fresh
    each time the preview redraws, so an Advanced-window edit made after this dialog was
    first opened is picked up immediately, not frozen at whatever it was on open.
    """
    if state.path_choice == "analytical_shape":
        thickness = state.shape_params.get("Thickness")
        if isinstance(thickness, int | float):
            return float(thickness)
    override = state.plm_overrides.get("bilayerThickness")
    if isinstance(override, int | float):
        return float(override)
    return _DEFAULT_THICKNESS


def _gro_title(gro_path: str) -> str:
    """A .gro file's own first line (its title comment) - the exact name PCG itself gives
    this structure as a MolType when `include`d (`GenerateMolType.cpp:100`: `GF.GetTitle()`,
    not any residue name), so `[Protein List]`'s own `ProteinName` column has to match this,
    not the protein's chemistry.
    """
    with open(gro_path) as f:
        return f.readline().strip()


class AddProteinDialog(QDialog):
    def __init__(
        self,
        state: WizardState,
        next_type_id: int,
        existing: ProteinSpec | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._state = state
        self._type_id = next_type_id if existing is None else existing.type_id
        self._gro_path = ""
        self._positions = None
        self._result: ProteinSpec | None = None

        self.setWindowTitle("Add protein" if existing is None else "Edit protein")
        available = self.screen().availableGeometry()
        self.resize(
            min(_DIALOG_SIZE[0], available.width() - _SCREEN_MARGIN),
            min(_DIALOG_SIZE[1], available.height() - _SCREEN_MARGIN),
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        path_row = QHBoxLayout()
        self._path_label = QLabel("No structure selected.")
        self._path_label.setStyleSheet("color: #555;")
        self._path_label.setWordWrap(True)
        path_row.addWidget(self._path_label, stretch=1)
        load_button = QPushButton("Load .gro")
        load_button.clicked.connect(self._on_load)
        path_row.addWidget(load_button)
        layout.addLayout(path_row)

        body = QHBoxLayout()
        body.setSpacing(20)
        self._figure = Figure(figsize=(5, 5))
        self._figure.subplots_adjust(left=0.0, right=1.0, bottom=0.0, top=1.0)
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._canvas.setMinimumSize(_PREVIEW_MINIMUM_SIZE, _PREVIEW_MINIMUM_SIZE)
        self._axes = self._figure.add_subplot(projection="3d")
        body.addWidget(self._canvas, stretch=1)

        settings_widget = QWidget()
        settings_widget.setMaximumWidth(_SETTINGS_MAXIMUM_WIDTH)
        settings_column = QVBoxLayout(settings_widget)
        settings_column.setContentsMargins(0, 0, 0, 0)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)
        self._z0_box = FloatSpinBox(minimum=-50.0, maximum=50.0, value=0.0, step=0.1, decimals=2)
        self._z0_box.valueChanged.connect(self._redraw_preview)
        form.addRow("Z offset (nm, along the membrane normal):", self._z0_box)

        self._radius_box = FloatSpinBox(minimum=0.1, maximum=100.0, value=1.0, step=0.1, decimals=2)
        form.addRow("Exclusion radius (nm):", self._radius_box)

        self._count_box = IntSpinBox(minimum=1, maximum=10_000, value=1)
        form.addRow("Number of proteins:", self._count_box)

        self._ratio_box = FloatSpinBox(minimum=0.0, maximum=1.0, value=0.1, step=0.01, decimals=3)
        form.addRow("Surface coverage (Ratio):", self._ratio_box)

        curvature_row = QHBoxLayout()
        self._curvature_check = QCheckBox("Target a specific curvature")
        curvature_row.addWidget(self._curvature_check)
        self._curvature_box = FloatSpinBox(minimum=-10.0, maximum=10.0, value=0.0, step=0.01, decimals=3)
        self._curvature_box.setEnabled(False)
        self._curvature_check.toggled.connect(self._curvature_box.setEnabled)
        curvature_row.addWidget(self._curvature_box)
        form.addRow("", curvature_row)

        self._k_factor_box = FloatSpinBox(minimum=0.0, maximum=100.0, value=1.0, step=0.1, decimals=2)
        form.addRow("Curvature preference strength (k-factor):", self._k_factor_box)

        seed_row = QHBoxLayout()
        self._seed_check = QCheckBox("Fixed random seed")
        seed_row.addWidget(self._seed_check)
        self._seed_box = IntSpinBox()
        self._seed_box.setEnabled(False)
        self._seed_check.toggled.connect(self._seed_box.setEnabled)
        seed_row.addWidget(self._seed_box)
        form.addRow("", seed_row)

        settings_column.addLayout(form)
        settings_column.addStretch(1)
        body.addWidget(settings_widget)
        layout.addLayout(body, stretch=1)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons_row.addWidget(cancel_button)
        self._add_button = QPushButton("Add protein" if existing is None else "Save changes")
        mark_primary(self._add_button)
        self._add_button.setEnabled(False)
        self._add_button.clicked.connect(self._on_add_clicked)
        buttons_row.addWidget(self._add_button)
        layout.addLayout(buttons_row)

        if existing is not None:
            self._fill_from(existing)
        self._redraw_preview()

    def _fill_from(self, protein: ProteinSpec) -> None:
        self._z0_box.setValue(protein.z0)
        self._radius_box.setValue(protein.radius)
        self._count_box.setValue(protein.num_proteins)
        self._ratio_box.setValue(protein.ratio)
        self._curvature_check.setChecked(protein.target_curvature is not None)
        self._curvature_box.setValue(protein.target_curvature or 0.0)
        self._k_factor_box.setValue(protein.k_factor)
        self._seed_check.setChecked(protein.seed is not None)
        self._seed_box.setValue(protein.seed or 0)
        self._load_structure(protein.gro_path)

    def result_protein(self) -> ProteinSpec | None:
        """The ProteinSpec built on Add - only meaningful after exec() returns Accepted."""
        return self._result

    def _on_load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select protein structure", "", "GRO files (*.gro);;All files (*)")
        if path:
            self._load_structure(path)

    def _load_structure(self, path: str) -> None:
        """Reads `path`'s positions for the preview; Add stays disabled until one loads."""
        import MDAnalysis as mda

        try:
            universe = mda.Universe(path)
        except Exception as exc:  # noqa: BLE001 - surfaced to the user, not a programming error
            self._path_label.setText(f"Could not read {path}: {exc}")
            return
        self._gro_path = path
        self._positions = universe.atoms.positions.copy()
        self._path_label.setText(path)
        self._add_button.setEnabled(True)
        self._redraw_preview()

    def _redraw_preview(self, *_args: object) -> None:
        self._axes.clear()
        thickness = _current_bilayer_thickness(self._state)
        z0 = self._z0_box.value()

        if self._positions is not None:
            # TS2CG/Angstrom .gro positions are nm*10 - this preview only cares about
            # relative shape, so positions are shown in the same units the .gro file
            # already uses (nm, matching MDAnalysis's own unit convention), offset by
            # Z0 along z the same way GenProtein's own `DH = Normal * Z0` does for a
            # locally-flat approximation of the membrane normal.
            positions = self._positions / 10.0 + [0.0, 0.0, z0]
            self._axes.scatter(positions[:, 0], positions[:, 1], positions[:, 2], s=4, c="#2a6fdb")
            span = max(float(np.ptp(positions[:, :2])), 1.0) * 0.75
            cx, cy = positions[:, 0].mean(), positions[:, 1].mean()
        else:
            span = 5.0
            cx = cy = 0.0

        x = [cx - span, cx + span]
        y = [cy - span, cy + span]
        X, Y = np.meshgrid(x, y)
        self._axes.plot_surface(X, Y, np.full_like(X, thickness / 2), color="black", alpha=0.15)
        self._axes.plot_surface(X, Y, np.full_like(X, -thickness / 2), color="black", alpha=0.15)

        z_low, z_high = -thickness / 2, thickness / 2
        if self._positions is not None:
            z_low = min(z_low, float(positions[:, 2].min()))
            z_high = max(z_high, float(positions[:, 2].max()))
        self._axes.set_xlim(*x)
        self._axes.set_ylim(*y)
        self._axes.set_zlim(z_low, z_high)
        self._axes.set_box_aspect((2 * span, 2 * span, z_high - z_low), zoom=_PREVIEW_ZOOM)
        self._axes.tick_params(labelsize=7, pad=0)
        self._axes.set_xlabel("x (nm)", fontsize=8, labelpad=0)
        self._axes.set_ylabel("y (nm)", fontsize=8, labelpad=0)
        self._axes.set_zlabel("z (nm)", fontsize=8, labelpad=0)
        self._canvas.draw_idle()

    def _on_add_clicked(self) -> None:
        self._result = ProteinSpec(
            type_id=self._type_id,
            name=_gro_title(self._gro_path),
            gro_path=self._gro_path,
            radius=self._radius_box.value(),
            num_proteins=self._count_box.value(),
            target_curvature=self._curvature_box.value() if self._curvature_check.isChecked() else None,
            k_factor=self._k_factor_box.value(),
            seed=self._seed_box.value() if self._seed_check.isChecked() else None,
            ratio=self._ratio_box.value(),
            z0=self._z0_box.value(),
        )
        self.accept()
