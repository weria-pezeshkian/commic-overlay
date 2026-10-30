"""Tests for calm/availability.py::calm_unavailable_reason."""

from __future__ import annotations

from commic_overlay.calm.availability import calm_unavailable_reason


def test_calm_unavailable_reason_none_when_calm_is_on_path_and_importable() -> None:
    # This test suite itself only runs in an environment with CALM
    # actually installed (see tests/README-equivalent note in pyproject.toml's
    # own Development section) - a real, not mocked, positive case.
    import shutil

    assert shutil.which("CALM") is not None, "test environment must have CALM installed"
    assert calm_unavailable_reason() is None


def test_calm_unavailable_reason_names_the_missing_command(monkeypatch) -> None:
    monkeypatch.setattr("shutil.which", lambda name: None)
    reason = calm_unavailable_reason()
    assert reason is not None
    assert "not found on PATH" in reason
