"""Pure geometry for `point_picker_3d.py`: which points to draw for a camera, which point a
click hit, and which points a selected center covers.

Occlusion is a coarse depth buffer: points are binned into square screen cells a few point
spacings wide, and a point is drawn when it lies within a few spacings of the closest depth
in its cell. It needs no surface orientation, so it works from both sides of an open sheet.

Bundling bins points into cubes on a grid anchored to the whole cloud, using the finest
cube size that stays within `max_points`. Each label bundles separately, which keeps a small
domain visible when zoomed out.
"""

from __future__ import annotations

import numpy as np

MAX_VISIBLE_POINTS = 100
PORE_NORMAL_CUTOFF = 6.0  # nm, the `dist*cosT<6` test in TS2CG's `ExcludePointsUsingExclusion`

_OCCLUSION_CELL_SPACINGS = 2.0
_LAYER_DEPTH_SPACINGS = 4.0
_SPACING_SAMPLE_SIZE = 200
_BUNDLING_LEVELS_PER_DOUBLING = 4
_MAX_BUNDLING_LEVEL = 60  # 2**15 cubes per side, which keeps `_cell_keys`' fields from overlapping


def estimate_spacing(coordinates: np.ndarray) -> float:
    """Median nearest-neighbour distance of an evenly stepped sample of `coordinates`."""
    step = max(1, len(coordinates) // _SPACING_SAMPLE_SIZE)
    distances = []
    for point in coordinates[::step]:
        squared = np.sum((coordinates - point) ** 2, axis=1)
        squared = squared[squared > 0]
        if len(squared) > 0:
            distances.append(np.sqrt(squared.min()))
    return float(np.median(distances)) if distances else 1.0


def view_basis(azim_degrees: float, elev_degrees: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(right, up, toward_camera) unit vectors for matplotlib's `Axes3D.azim`/`Axes3D.elev`."""
    azim = np.radians(azim_degrees)
    elev = np.radians(elev_degrees)
    toward_camera = np.array([np.cos(elev) * np.cos(azim), np.cos(elev) * np.sin(azim), np.sin(elev)])
    right = np.array([-np.sin(azim), np.cos(azim), 0.0])
    return right, np.cross(toward_camera, right), toward_camera


def closest_layer_mask(coordinates: np.ndarray, azim_degrees: float, elev_degrees: float, spacing: float) -> np.ndarray:
    """Boolean mask of the points in the surface layer closest to the camera."""
    right, up, toward_camera = view_basis(azim_degrees, elev_degrees)
    cell_size = _OCCLUSION_CELL_SPACINGS * spacing
    columns = np.floor(coordinates @ right / cell_size).astype(np.int64)
    rows = np.floor(coordinates @ up / cell_size).astype(np.int64)
    cell_keys = (columns - columns.min()) * (rows.max() - rows.min() + 1) + (rows - rows.min())
    _, cell_of_point = np.unique(cell_keys, return_inverse=True)

    depth = coordinates @ toward_camera
    closest_depth = np.full(cell_of_point.max() + 1, -np.inf)
    np.maximum.at(closest_depth, cell_of_point, depth)
    return depth >= closest_depth[cell_of_point] - _LAYER_DEPTH_SPACINGS * spacing


def points_in_view(coordinates: np.ndarray, limits: np.ndarray) -> np.ndarray:
    """Boolean mask of the points inside `limits`, shaped (3, 2) as (low, high) per axis."""
    return np.all((coordinates >= limits[:, 0]) & (coordinates <= limits[:, 1]), axis=1)


def _cell_keys(offsets: np.ndarray, groups: np.ndarray, cell_size: float) -> np.ndarray:
    cells = np.floor(offsets / cell_size).astype(np.int64)
    return (cells[:, 0] << 47) | (cells[:, 1] << 31) | (cells[:, 2] << 15) | groups


def _finest_keys_within(offsets: np.ndarray, groups: np.ndarray, span: float, max_points: int) -> np.ndarray:
    """Bisects cube sizes for the finest whose occupied cell count stays within `max_points`."""
    low, high = 0, _MAX_BUNDLING_LEVEL
    while low < high:
        level = (low + high + 1) // 2
        cell_size = span / 2 ** (level / _BUNDLING_LEVELS_PER_DOUBLING)
        if len(np.unique(_cell_keys(offsets, groups, cell_size))) <= max_points:
            low = level
        else:
            high = level - 1
    return _cell_keys(offsets, groups, span / 2 ** (low / _BUNDLING_LEVELS_PER_DOUBLING))


def bundle_to_representatives(
    coordinates: np.ndarray, indices: np.ndarray, labels: np.ndarray, max_points: int = MAX_VISIBLE_POINTS
) -> np.ndarray:
    """Reduces `indices` to at most `max_points` real points: each bundle is represented by
    the member nearest its centroid. `labels` holds one value per row of `coordinates`."""
    if len(indices) <= max_points:
        return indices

    origin = coordinates.min(axis=0)
    span = max(float(np.ptp(coordinates, axis=0).max()), 1e-9) * 1.001
    subset = coordinates[indices]
    _, groups = np.unique(labels[indices], return_inverse=True)
    keys = _finest_keys_within(subset - origin, groups.astype(np.int64), span, max_points)

    _, bundle_of_point = np.unique(keys, return_inverse=True)
    sizes = np.bincount(bundle_of_point)
    centroids = np.stack(
        [np.bincount(bundle_of_point, weights=subset[:, axis]) / sizes for axis in range(3)], axis=1
    )
    distance = np.sum((subset - centroids[bundle_of_point]) ** 2, axis=1)
    order = np.lexsort((distance, bundle_of_point))
    _, first_of_bundle = np.unique(bundle_of_point[order], return_index=True)
    return indices[order[first_of_bundle]][:max_points]


def select_visible_points(
    coordinates: np.ndarray,
    labels: np.ndarray,
    azim_degrees: float,
    elev_degrees: float,
    limits: np.ndarray,
    spacing: float,
    max_points: int = MAX_VISIBLE_POINTS,
) -> np.ndarray:
    """Indices to draw: the closest layer inside `limits`, bundled to at most `max_points`."""
    in_layer = closest_layer_mask(coordinates, azim_degrees, elev_degrees, spacing)
    visible = np.nonzero(in_layer & points_in_view(coordinates, limits))[0]
    return bundle_to_representatives(coordinates, visible, labels, max_points)


def nearest_screen_point(
    screen_points: np.ndarray, position: tuple[float, float], tolerance: float | None = None
) -> int | None:
    """Row of `screen_points` nearest `position`, or None when no row lies within `tolerance`."""
    if len(screen_points) == 0:
        return None
    distances = np.linalg.norm(screen_points - np.asarray(position), axis=1)
    nearest = int(np.argmin(distances))
    if tolerance is not None and distances[nearest] > tolerance:
        return None
    return nearest


def points_within_radius(coordinates: np.ndarray, center: int, radius: float, box: np.ndarray) -> np.ndarray:
    """Boolean mask of the points a circular domain around `center` covers: euclidean distance
    under the minimum-image convention, the distance DAI's periodic KDTree measures."""
    delta = coordinates - coordinates[center]
    delta -= box * np.round(delta / box)
    return np.sum(delta**2, axis=1) <= radius**2


def points_within_pore(coordinates: np.ndarray, normals: np.ndarray, center: int, radius: float) -> np.ndarray:
    """Boolean mask of the points an exclusion at `center` covers, with the in-plane distance
    and normal cutoff of TS2CG's `ExcludePointsUsingExclusion`."""
    delta = coordinates - coordinates[center]
    along_normal = delta @ normals[center]
    in_plane_squared = np.sum(delta**2, axis=1) - along_normal**2
    return (in_plane_squared <= radius**2) & (np.abs(along_normal) < PORE_NORMAL_CUTOFF)
