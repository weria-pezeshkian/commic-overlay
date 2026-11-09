"""AddProteinDialog: load a protein .gro, see it placed against the two leaflet planes the
way PCG places it, and collect everything one `ProteinSpec` needs - INU's own placement
fields (radius, count, optional curvature targeting, seed) plus the `[Protein List]` entry it
becomes (`Z0`, the depth, measured from the outer leaflet's points; `Ratio`, always
collected even though this placement path doesn't consult it at runtime - PCG's own
`[Protein List]` parser requires the line regardless), and the orientation the run applies
to a copy of the structure: the principal-axis alignment, then the rotation about x and y
(`ts2cg_bridge/protein_structure.py`).

Opened with an `existing` protein, it edits that protein: every field starts from its values,
its structure is reloaded, and the result keeps its type id.
"""

from __future__ import annotations

from pathlib import Path

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
from ...widgets.angle_control import AngleControl
from ...widgets.float_spinbox import FloatSpinBox
from ...widgets.scroll_spinbox import IntSpinBox
from ..state import ProteinSpec, WizardState
from ..ts2cg_bridge.point_placement import outer_leaflet_height, placed_protein_positions
from ..ts2cg_bridge.protein_structure import (
    GroStructure,
    footprint_diameter,
    molecule_name,
    read_gro,
    rotate_about_center,
)

_DIALOG_SIZE = (1180, 700)
_SCREEN_MARGIN = 80  # kept free around the dialog when the screen is smaller than _DIALOG_SIZE
_PREVIEW_MINIMUM_SIZE = 420
_SETTINGS_MAXIMUM_WIDTH = 560
_PREVIEW_ZOOM = 0.85  # shrinks the 3D box inside the canvas so the tick labels fit
_PREVIEW_MARGIN = 1.0  # nm of membrane shown around the protein's footprint
_EMPTY_HALF_SPAN = 5.0  # nm of membrane shown on each side before a structure loads
_MIDPLANE_STYLE = {"color": "#777777", "linestyle": "--", "linewidth": 0.8}
_HINT_STYLE = "color: #555;"
_ROTATION_HINT = (
    "The rotations turn the structure about its center of geometry, about x first, then about "
    "y, starting from the file's orientation, or from the aligned one when Align z to principal "
    "axis is ticked; 180° about x flips it. The run writes the turned structure to a new .gro "
    "in TS2CG_build/ and builds the membrane with it."
)
_RADIUS_TOOLTIP = (
    "TS2CG's INU puts each protein at a random point at least this far from the center of "
    "every protein placed before it (its --radius)."
)
_ALIGN_TOOLTIP = (
    "Turns the protein so its first principal component, the direction its beads spread along "
    "most, points along z, the membrane normal, with the end that pointed up in the file on "
    "top. Ticking or unticking it sets both rotations to 0°."
)


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
        self._structure: GroStructure | None = None
        self._result: ProteinSpec | None = None
        # A new protein's distance follows its footprint until the user sets one.
        self._radius_follows_footprint = existing is None

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
        form.addRow("Z0 (nm, from the outer leaflet along the normal):", self._z0_box)
        self._z0_hint = QLabel()
        self._z0_hint.setWordWrap(True)
        self._z0_hint.setStyleSheet(_HINT_STYLE)
        form.addRow(self._z0_hint)

        self._align_check = QCheckBox("Align z to principal axis")
        self._align_check.setToolTip(_ALIGN_TOOLTIP)
        self._align_check.toggled.connect(self._on_align_toggled)
        form.addRow("", self._align_check)
        self._rotation_x = AngleControl()
        self._rotation_x.valueChanged.connect(self._redraw_preview)
        form.addRow("Rotation about x:", self._rotation_x)
        self._rotation_y = AngleControl()
        self._rotation_y.valueChanged.connect(self._redraw_preview)
        form.addRow("Rotation about y:", self._rotation_y)
        rotation_hint = QLabel(_ROTATION_HINT)
        rotation_hint.setWordWrap(True)
        rotation_hint.setStyleSheet(_HINT_STYLE)
        form.addRow(rotation_hint)

        self._radius_box = FloatSpinBox(minimum=0.1, maximum=100.0, value=1.0, step=0.1, decimals=2)
        self._radius_box.setToolTip(_RADIUS_TOOLTIP)
        self._radius_box.valueChanged.connect(self._on_radius_edited)
        form.addRow("Minimum distance between protein centers (nm):", self._radius_box)
        self._radius_hint = QLabel()
        self._radius_hint.setWordWrap(True)
        self._radius_hint.setStyleSheet(_HINT_STYLE)
        self._radius_hint.setVisible(False)
        form.addRow(self._radius_hint)

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

        # Enter in a field commits the typed value and leaves every button unclicked.
        for button in self.findChildren(QPushButton):
            button.setAutoDefault(False)

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
        self._align_check.blockSignals(True)  # keeps the protein's own rotations
        self._align_check.setChecked(protein.align_principal_axis)
        self._align_check.blockSignals(False)
        self._rotation_x.setValue(protein.rotation_x)
        self._rotation_y.setValue(protein.rotation_y)
        self._load_structure(protein.gro_path)

    def result_protein(self) -> ProteinSpec | None:
        """The ProteinSpec built on Add - only meaningful after exec() returns Accepted."""
        return self._result

    def _on_load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select protein structure", "", "GRO files (*.gro);;All files (*)")
        if path:
            self._load_structure(path)

    def _load_structure(self, path: str) -> None:
        """Reads `path` the way PCG reads it, for the preview; Add stays disabled until one loads."""
        try:
            structure = read_gro(Path(path))
        except (OSError, ValueError, IndexError) as exc:
            self._path_label.setText(f"Could not read {path}: {exc}")
            return
        self._gro_path = path
        self._structure = structure
        self._path_label.setText(path)
        self._add_button.setEnabled(True)
        self._redraw_preview()

    def _on_radius_edited(self, _value: float) -> None:
        self._radius_follows_footprint = False

    def _update_footprint(self, oriented: np.ndarray) -> None:
        """Shows the oriented protein's footprint, and sets the distance to it while the
        distance follows the footprint."""
        footprint = footprint_diameter(oriented)
        if self._radius_follows_footprint:
            self._radius_box.blockSignals(True)
            self._radius_box.setValue(footprint)
            self._radius_box.blockSignals(False)
            text = (
                f"Set to this protein's footprint, {footprint:.2f} nm across in this orientation, so "
                "copies cannot overlap. It follows the orientation until you change it."
            )
        else:
            text = (
                f"This protein's footprint is {footprint:.2f} nm across in this orientation; a "
                "smaller distance lets copies overlap."
            )
        self._radius_hint.setText(text)
        self._radius_hint.setVisible(True)

    def _on_align_toggled(self, _checked: bool) -> None:
        """Sets both rotations to 0°, so they turn the protein from its new starting orientation."""
        self._rotation_x.setValue(0.0)
        self._rotation_y.setValue(0.0)
        self._redraw_preview()

    def _redraw_preview(self, *_args: object) -> None:
        """Draws the protein where PCG puts it on a flat stretch of membrane: the midplane at
        z = 0 (dashed), the two leaflets' point planes at ± the outer leaflet's height."""
        self._axes.clear()
        height = outer_leaflet_height(self._state)
        self._z0_hint.setText(
            f"PCG puts the protein's center of geometry on the outer leaflet's points, {height:.2f} nm "
            f"above the membrane midplane, then moves it by Z0 along the normal. Z0 = {-height:.2f} "
            "centers it in the bilayer."
        )

        if self._structure is not None:
            rotated = rotate_about_center(
                self._structure.positions,
                self._rotation_x.value(),
                self._rotation_y.value(),
                self._align_check.isChecked(),
            )
            self._update_footprint(rotated)
            positions = placed_protein_positions(rotated, height, self._z0_box.value())
            self._axes.scatter(positions[:, 0], positions[:, 1], positions[:, 2], s=4, c="#2a6fdb")
            span = float(np.abs(positions[:, :2]).max()) + _PREVIEW_MARGIN
        else:
            span = _EMPTY_HALF_SPAN

        x = [-span, span]
        y = [-span, span]
        X, Y = np.meshgrid(x, y)
        self._axes.plot_surface(X, Y, np.full_like(X, height), color="black", alpha=0.15)
        self._axes.plot_surface(X, Y, np.full_like(X, -height), color="black", alpha=0.15)
        self._axes.plot([-span, span, span, -span, -span], [-span, -span, span, span, -span], 0.0, **_MIDPLANE_STYLE)

        z_low, z_high = -height, height
        if self._structure is not None:
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
        if self._structure is None:
            return
        self._result = ProteinSpec(
            type_id=self._type_id,
            name=molecule_name(self._structure.title),
            gro_path=self._gro_path,
            radius=self._radius_box.value(),
            num_proteins=self._count_box.value(),
            target_curvature=self._curvature_box.value() if self._curvature_check.isChecked() else None,
            k_factor=self._k_factor_box.value(),
            seed=self._seed_box.value() if self._seed_check.isChecked() else None,
            ratio=self._ratio_box.value(),
            z0=self._z0_box.value(),
            align_principal_axis=self._align_check.isChecked(),
            rotation_x=self._rotation_x.value(),
            rotation_y=self._rotation_y.value(),
        )
        self.accept()
