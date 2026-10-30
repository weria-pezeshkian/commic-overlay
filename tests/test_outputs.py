"""Tests for calm_bridge/outputs.py."""

from __future__ import annotations

from pathlib import Path

from commic_overlay.calm.calm_bridge import outputs


def test_full_output_dir_is_a_fixed_subdirectory_name(tmp_path: Path) -> None:
    assert outputs.full_output_dir(tmp_path) == tmp_path / "CALM_full"


def test_lipids_output_dir_is_a_fixed_subdirectory_name(tmp_path: Path) -> None:
    assert outputs.lipids_output_dir(tmp_path) == tmp_path / "CALM_lipids"


def test_output_dir_would_be_overwritten_false_when_missing(tmp_path: Path) -> None:
    assert outputs.output_dir_would_be_overwritten(tmp_path / "nope") is False


def test_output_dir_would_be_overwritten_false_when_empty(tmp_path: Path) -> None:
    target = tmp_path / "empty_dir"
    target.mkdir()
    assert outputs.output_dir_would_be_overwritten(target) is False


def test_output_dir_would_be_overwritten_true_when_populated(tmp_path: Path) -> None:
    target = tmp_path / "populated_dir"
    target.mkdir()
    (target / "Amn.npy").write_bytes(b"x")
    assert outputs.output_dir_would_be_overwritten(target) is True


def test_plot_modes_matches_calm_map_plots_own_mode_choices() -> None:
    # CALM/map/plot.py's own --mode choices are exactly these four (it
    # also fits Z_fitted/principal_directions via --method, but neither
    # has a 'CALM map plot' --mode of its own - see outputs.py's comment).
    assert outputs.PLOT_MODES == ("mean", "gaussian", "principal", "thickness")
