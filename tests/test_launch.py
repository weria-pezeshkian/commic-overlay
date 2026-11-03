"""Tests for launch.py's launch-directory detection."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from commic_overlay.launch import launch_directory


class _Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_a_terminal_stream_gives_the_current_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert launch_directory((io.StringIO(), _Terminal(), None)) == tmp_path


def test_no_terminal_stream_gives_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert launch_directory((io.StringIO(), io.StringIO(), None)) is None
    assert launch_directory((None, None, None)) is None
