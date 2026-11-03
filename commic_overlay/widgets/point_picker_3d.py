"""PointPicker3D: the 3D point view in the Place Domains operation dialogs.

matplotlib (`FigureCanvasQTAgg`, as in `ts2cg/pages/add_protein_dialog.py`) with an
orthographic camera. Left drag rotates, scrolling zooms towards the cursor. A left click
selects the nearest drawn point and shift-click adds to the selection. Every selected point
paints the region it would cover in the current domain color and draws a ring of that radius,
which stays readable when bundling leaves few points inside the region.

`point_picker_math.py` holds the geometry.
"""

from __future__ import annotations

import matplotlib
import numpy as np

matplotlib.use("QtAgg")
from matplotlib.backend_bases import MouseEvent  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402
from mpl_toolkits.mplot3d import proj3d  # noqa: E402
from PySide6.QtCore import Qt, Signal  # noqa: E402
from PySide6.QtWidgets import QVBoxLayout, QWidget  # noqa: E402

from .point_picker_math import (  # noqa: E402
    estimate_spacing,
    nearest_screen_point,
    points_within_pore,
    points_within_radius,
    select_visible_points,
)

_POINT_SIZE = 18
_SELECTED_SIZE = 60
_RING_SEGMENTS = 48
_PICK_TOLERANCE_PIXELS = 14
_CLICK_SLOP_PIXELS = 4
_ZOOM_STEP = 0.8
_VIEW_MARGIN = 1.1
_DEFAULT_ELEVATION = 35
_DEFAULT_AZIMUTH = -60
_UNLABELLED_COLOR = "#b0b0b0"
_PAINTED_LABEL = -1
_SELECTED_LABEL = -2


class PointPicker3D(QWidget):
    """`coordinates` and `normals` describe one leaflet (nm). `labels` holds one integer per
    point and `label_colors` maps those integers to colors. `pore=True` paints with the
    exclusion criterion and the default paints a circular domain; `selectable=False` makes the
    view display-only."""

    selection_changed = Signal()

    def __init__(
        self,
        coordinates: np.ndarray,
        normals: np.ndarray,
        box: np.ndarray,
        labels: np.ndarray,
        label_colors: dict[int, str],
        *,
        pore: bool = False,
        multi_select: bool = True,
        selectable: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._coordinates = coordinates
        self._normals = normals
        self._box = box
        self._labels = labels
        self._label_colors = label_colors
        self._pore = pore
        self._multi_select = multi_select
        self._selectable = selectable
        self._selected: list[int] = []
        self._radius = 1.0
        self._domain_color = _UNLABELLED_COLOR
        self._spacing = estimate_spacing(coordinates)
        self._press_position: tuple[float, float] | None = None
        self._artists: list[object] = []
        self._visible_indices = np.arange(0)
        self._drawn_camera: tuple[float, ...] = ()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._figure = Figure(figsize=(5, 4))
        self._canvas = FigureCanvasQTAgg(self._figure)
        self._axes = self._figure.add_subplot(projection="3d", proj_type="ortho")
        self._axes.set_box_aspect((1, 1, 1))
        self._axes.view_init(elev=_DEFAULT_ELEVATION, azim=_DEFAULT_AZIMUTH)
        self._axes.autoscale(enable=False)
        self._axes.set_xlabel("x (nm)")
        self._axes.set_ylabel("y (nm)")
        self._axes.set_zlabel("z (nm)")
        layout.addWidget(self._canvas)

        center = (coordinates.min(axis=0) + coordinates.max(axis=0)) / 2
        half_span = max(float(np.ptp(coordinates, axis=0).max()), 1e-9) / 2 * _VIEW_MARGIN
        self._full_limits = np.stack([center - half_span, center + half_span], axis=1)
        self._set_limits(self._full_limits)

        self._canvas.mpl_connect("button_press_event", self._on_press)
        self._canvas.mpl_connect("button_release_event", self._on_release)
        self._canvas.mpl_connect("motion_notify_event", self._on_motion)
        self._canvas.mpl_connect("scroll_event", self._on_scroll)

        self._refresh_view()

    def selected_point_ids(self) -> list[int]:
        return list(self._selected)

    def visible_point_ids(self) -> np.ndarray:
        return self._visible_indices.copy()

    def set_radius(self, radius: float) -> None:
        self._radius = radius
        self._refresh_view()

    def set_domain_color(self, color: str) -> None:
        self._domain_color = color
        self._refresh_view()

    def set_selection(self, point_ids: list[int]) -> None:
        self._selected = list(point_ids)
        self._refresh_view()
        self.selection_changed.emit()

    def _limits(self) -> np.ndarray:
        return np.array([self._axes.get_xlim3d(), self._axes.get_ylim3d(), self._axes.get_zlim3d()])

    def _set_limits(self, limits: np.ndarray) -> None:
        self._axes.set_xlim3d(*limits[0])
        self._axes.set_ylim3d(*limits[1])
        self._axes.set_zlim3d(*limits[2])

    def _camera(self) -> tuple[float, ...]:
        return (self._axes.azim, self._axes.elev, *self._limits().ravel().tolist())

    def _screen_positions(self) -> np.ndarray:
        """Display pixels of the drawn points, in the frame of `MouseEvent.x`/`.y`."""
        visible = self._coordinates[self._visible_indices]
        x, y, _ = proj3d.proj_transform(visible[:, 0], visible[:, 1], visible[:, 2], self._axes.get_proj())
        return self._axes.transData.transform(np.column_stack([np.asarray(x), np.asarray(y)]))

    def _on_press(self, event: MouseEvent) -> None:
        self._press_position = (event.x, event.y) if event.button == 1 else None

    def _on_release(self, event: MouseEvent) -> None:
        press = self._press_position
        self._press_position = None
        if press is None or not self._selectable:
            return
        if abs(event.x - press[0]) + abs(event.y - press[1]) > _CLICK_SLOP_PIXELS:
            return
        hit = nearest_screen_point(self._screen_positions(), (event.x, event.y), _PICK_TOLERANCE_PIXELS)
        if hit is None:
            return
        shift_held = bool(event.guiEvent.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        self._apply_click(int(self._visible_indices[hit]), shift_held)

    def _apply_click(self, point_id: int, shift_held: bool) -> None:
        if not (self._multi_select and shift_held):
            self._selected = [point_id]
        elif point_id in self._selected:
            self._selected.remove(point_id)
        else:
            self._selected.append(point_id)
        self._refresh_view()
        self.selection_changed.emit()

    def _on_motion(self, _event: MouseEvent) -> None:
        if self._camera() != self._drawn_camera:
            self._refresh_view()

    def _on_scroll(self, event: MouseEvent) -> None:
        limits = self._limits()
        center = limits.mean(axis=1)
        half_spans = (limits[:, 1] - limits[:, 0]) / 2
        factor = _ZOOM_STEP if event.button == "up" else 1 / _ZOOM_STEP

        if half_spans[0] * factor >= (self._full_limits[0, 1] - self._full_limits[0, 0]) / 2:
            self._set_limits(self._full_limits)
        else:
            hit = nearest_screen_point(self._screen_positions(), (event.x, event.y))
            target = center if hit is None else self._coordinates[self._visible_indices[hit]]
            new_center = target + (center - target) * factor
            self._set_limits(np.stack([new_center - half_spans * factor, new_center + half_spans * factor], axis=1))
        self._refresh_view()

    def _region_mask(self, point_id: int) -> np.ndarray:
        if self._pore:
            return points_within_pore(self._coordinates, self._normals, point_id, self._radius)
        return points_within_radius(self._coordinates, point_id, self._radius, self._box)

    def _display_labels(self) -> np.ndarray:
        labels = self._labels.copy()
        for point_id in self._selected:
            labels[self._region_mask(point_id)] = _PAINTED_LABEL
        labels[self._selected] = _SELECTED_LABEL
        return labels

    def _label_color(self, label: int) -> str:
        if label in (_PAINTED_LABEL, _SELECTED_LABEL):
            return self._domain_color
        return self._label_colors.get(label, _UNLABELLED_COLOR)

    def _refresh_view(self) -> None:
        labels = self._display_labels()
        self._drawn_camera = self._camera()
        self._visible_indices = select_visible_points(
            self._coordinates, labels, self._axes.azim, self._axes.elev, self._limits(), self._spacing
        )

        for artist in self._artists:
            artist.remove()
        self._artists.clear()

        visible = self._coordinates[self._visible_indices]
        visible_labels = labels[self._visible_indices]
        self._artists.append(
            self._axes.scatter(
                visible[:, 0], visible[:, 1], visible[:, 2],
                s=np.where(visible_labels == _SELECTED_LABEL, _SELECTED_SIZE, _POINT_SIZE),
                c=[self._label_color(int(label)) for label in visible_labels],
                depthshade=False,
            )
        )
        for point_id in self._visible_indices[visible_labels == _SELECTED_LABEL]:
            self._artists.append(self._draw_ring(int(point_id)))
        self._canvas.draw_idle()

    def _draw_ring(self, point_id: int) -> object:
        """A circle of the current radius in the plane normal to `point_id`'s normal."""
        center = self._coordinates[point_id]
        normal = self._normals[point_id] / max(float(np.linalg.norm(self._normals[point_id])), 1e-9)
        reference = np.array([1.0, 0.0, 0.0]) if abs(normal[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        u = np.cross(normal, reference)
        u /= np.linalg.norm(u)
        v = np.cross(normal, u)
        theta = np.linspace(0, 2 * np.pi, _RING_SEGMENTS)
        ring = center + self._radius * (np.outer(np.cos(theta), u) + np.outer(np.sin(theta), v))
        return self._axes.plot(ring[:, 0], ring[:, 1], ring[:, 2], color=self._domain_color, alpha=0.7)[0]
