"""Building the preview point directory from a page, behind a modal progress dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QProgressDialog, QWidget

from ..state import WizardState
from ..ts2cg_bridge.preview_membrane import build_preview_point_dir, preview_is_current, prune_domain_ops


def ensure_preview(parent: QWidget, state: WizardState) -> int:
    """Builds `state`'s preview point directory when it is stale, showing a progress dialog
    over `parent` meanwhile, then prunes the domain operations the rebuild invalidated.
    Returns how many operations were pruned; raises whatever the build raises."""
    previous_signature = state.preview_signature
    progress = None
    if not preview_is_current(state):
        progress = QProgressDialog("Building preview…", "", 0, 0, parent)
        progress.setCancelButton(None)
        progress.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress.setMinimumDuration(0)
        progress.show()
        QApplication.processEvents()
    try:
        build_preview_point_dir(state)
    finally:
        if progress is not None:
            progress.close()
    return prune_domain_ops(state, previous_signature)
