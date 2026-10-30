"""Tests for calm_bridge/progress.py::parse_latest_progress, against tqdm's real output shape."""

from __future__ import annotations

from commic_overlay.calm.calm_bridge.progress import ProgressState, parse_latest_progress


def test_parses_a_bare_tqdm_bar_with_no_description() -> None:
    text = " 45%|████▌     | 45/100 [00:12<00:15,  3.33it/s]"
    assert parse_latest_progress(text) == ProgressState(description=None, percent=45, current=45, total=100)


def test_parses_a_tqdm_bar_with_a_description() -> None:
    text = "fitting surfaces:  20%|##        | 2/10 [00:01<00:04,  2.00it/s]"
    result = parse_latest_progress(text)
    assert result == ProgressState(description="fitting surfaces", percent=20, current=2, total=10)


def test_returns_the_latest_of_several_carriage_return_separated_updates() -> None:
    # Exactly the shape a real QProcess chunk can arrive in - tqdm
    # redraws its own bar in place via \r, so several stale updates can
    # land in one chunk; only the last one matters.
    text = (
        "\rfitting surfaces:   0%|          | 0/3 [00:00<?, ?it/s]"
        "\rfitting surfaces:  33%|###       | 1/3 [00:00<00:01,  1.0it/s]"
        "\rfitting surfaces: 100%|##########| 3/3 [00:00<00:00, 98.54it/s]\n"
    )
    result = parse_latest_progress(text)
    assert result == ProgressState(description="fitting surfaces", percent=100, current=3, total=3)


def test_none_when_text_has_no_progress_bar() -> None:
    assert parse_latest_progress("Loading structure file...") is None
    assert parse_latest_progress("") is None
    assert parse_latest_progress("warning: something happened at 50% chance") is None
