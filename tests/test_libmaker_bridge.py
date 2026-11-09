"""Tests for ts2cg_bridge/libmaker_bridge.py - a stubbed `run_libmaker`, no real TS2CG call."""

from __future__ import annotations

from pathlib import Path

from commic_overlay.ts2cg.ts2cg_bridge.libmaker_bridge import build_lib_file, libmaker_argv

_POPC_ITP = """\
[ moleculetype ]
POPC 1

[ atoms ]
1 Q1 1 POPC NC3 1 1.0
2 Q5 1 POPC PO4 2 -1.0
3 SN4a 1 POPC GL1 3 0.0
4 C1 1 POPC C1A 4 0.0

[ bonds ]
1 2 1
2 3 1
3 4 1
"""

_CHOL_ITP = """\
[ moleculetype ]
CHOL 1

[ atoms ]
1 P1 1 CHOL ROH 1 0.0
2 SC1 1 CHOL R1 2 0.0

[ bonds ]
1 2 1
"""


def _write(path: Path, content: str) -> None:
    path.write_text(content)


class _StubLibmaker:
    """A fake `run_libmaker` writing `{isolated_itp.stem}_lib.txt` - mirrors `maker_itp`'s
    own output naming, scoped to whichever single-molecule itp file it was actually
    called with (the real per-molecule isolation, not the original shared source file).
    Records each (itp stem, base) call so a test can assert the detected anchor bead,
    and each call's options."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.options: list[dict[str, object]] = []

    def __call__(self, itp_path: Path, base: str, out_dir: Path, options: dict[str, object]) -> None:
        self.calls.append((itp_path.stem, base))
        self.options.append(options)
        (out_dir / f"{itp_path.stem}_lib.txt").write_text(f"[{itp_path.stem}]\nanchor={base}\n")


def _stub_writing() -> tuple[_StubLibmaker, list[tuple[str, str]]]:
    fake = _StubLibmaker()
    return fake, fake.calls


def _write_nothing(itp_path: Path, base: str, out_dir: Path, options: dict[str, object]) -> None:
    """A fake `run_libmaker` that runs but writes no snippet."""


def test_build_lib_file_converts_each_selected_lipid(tmp_path: Path) -> None:
    pc_itp = tmp_path / "pc.itp"
    _write(pc_itp, _POPC_ITP)
    lipid_to_itp = {"POPC": pc_itp}
    fake, calls = _stub_writing()

    result = build_lib_file(["POPC"], lipid_to_itp, tmp_path / "out.LIB", run_libmaker=fake)

    assert result.converted_lipids == ["POPC"]
    assert result.failed_lipids == []
    assert calls == [("POPC", "PO4")]  # PO4 is the real detected anchor (Q-class, highest rank)


def test_build_lib_file_isolates_each_molecule_even_from_the_same_source_file(tmp_path: Path) -> None:
    combined_itp = tmp_path / "combined.itp"
    _write(combined_itp, _POPC_ITP + "\n" + _CHOL_ITP)
    lipid_to_itp = {"POPC": combined_itp, "CHOL": combined_itp}
    fake, calls = _stub_writing()

    result = build_lib_file(["POPC", "CHOL"], lipid_to_itp, tmp_path / "out.LIB", run_libmaker=fake)

    assert set(result.converted_lipids) == {"POPC", "CHOL"}
    # Each got its own isolated itp (named after the molecule, not the shared source file)
    # and its own correctly-detected anchor - PO4 for POPC, ROH for CHOL.
    assert ("POPC", "PO4") in calls
    assert ("CHOL", "ROH") in calls


def test_build_lib_file_keeps_only_selected_lipids_in_output(tmp_path: Path) -> None:
    pc_itp = tmp_path / "pc.itp"
    _write(pc_itp, _POPC_ITP)
    lipid_to_itp = {"POPC": pc_itp}
    fake, _calls = _stub_writing()

    build_lib_file(["POPC"], lipid_to_itp, tmp_path / "out.LIB", run_libmaker=fake)

    content = (tmp_path / "out.LIB").read_text()
    assert "[POPC]" in content


def test_build_lib_file_reports_a_lipid_libmaker_silently_skipped(tmp_path: Path) -> None:
    pc_itp = tmp_path / "pc.itp"
    _write(pc_itp, _POPC_ITP)
    lipid_to_itp = {"POPC": pc_itp}

    result = build_lib_file(["POPC"], lipid_to_itp, tmp_path / "out.LIB", run_libmaker=_write_nothing)

    assert result.converted_lipids == []
    assert result.failed_lipids == ["POPC"]


def test_build_lib_file_reports_a_lipid_with_no_known_source_itp(tmp_path: Path) -> None:
    fake, _calls = _stub_writing()
    result = build_lib_file(["MYSTERY"], {}, tmp_path / "out.LIB", run_libmaker=fake)
    assert result.failed_lipids == ["MYSTERY"]
    assert result.converted_lipids == []


def test_build_lib_file_reports_a_lipid_not_actually_in_its_claimed_source_file(tmp_path: Path) -> None:
    pc_itp = tmp_path / "pc.itp"
    _write(pc_itp, _POPC_ITP)
    # Claims a molecule name that isn't really in pc.itp.
    lipid_to_itp = {"NOTREAL": pc_itp}
    fake, _calls = _stub_writing()

    result = build_lib_file(["NOTREAL"], lipid_to_itp, tmp_path / "out.LIB", run_libmaker=fake)

    assert result.failed_lipids == ["NOTREAL"]
    assert result.converted_lipids == []


def test_build_lib_file_writes_the_required_header_lines(tmp_path: Path) -> None:
    pc_itp = tmp_path / "pc.itp"
    _write(pc_itp, _POPC_ITP)
    lipid_to_itp = {"POPC": pc_itp}
    fake, _calls = _stub_writing()

    build_lib_file(["POPC"], lipid_to_itp, tmp_path / "out.LIB", run_libmaker=fake)

    content = (tmp_path / "out.LIB").read_text()
    assert content.startswith("Description Martini Map CG\nVersion Martini 3\n")


def test_build_lib_file_preserves_selection_order_in_output(tmp_path: Path) -> None:
    combined_itp = tmp_path / "combined.itp"
    _write(combined_itp, _POPC_ITP + "\n" + _CHOL_ITP)
    lipid_to_itp = {"POPC": combined_itp, "CHOL": combined_itp}
    fake, _calls = _stub_writing()

    build_lib_file(["CHOL", "POPC"], lipid_to_itp, tmp_path / "out.LIB", run_libmaker=fake)

    content = (tmp_path / "out.LIB").read_text()
    assert content.index("[CHOL]") < content.index("[POPC]")


def test_build_lib_file_passes_the_scaling_options_to_every_libmaker_call(tmp_path: Path) -> None:
    combined_itp = tmp_path / "combined.itp"
    _write(combined_itp, _POPC_ITP + "\n" + _CHOL_ITP)
    lipid_to_itp = {"POPC": combined_itp, "CHOL": combined_itp}
    fake = _StubLibmaker()

    build_lib_file(["POPC", "CHOL"], lipid_to_itp, tmp_path / "out.LIB", {"scalingz": 2.0}, run_libmaker=fake)

    assert fake.options == [{"scalingz": 2.0}, {"scalingz": 2.0}]


def test_libmaker_argv_adds_the_set_scaling_flags() -> None:
    argv = libmaker_argv(Path("POPC.itp"), "PO4", {"scalingz": 2.0, "scalingxy": 0.5})
    assert argv == [
        "TS2CG", "libmaker", "-sz", "2.0", "-sxy", "0.5", "-p", "POPC.itp", "-b", "PO4", "-o", "lib.txt",
    ]


def test_libmaker_argv_leaves_unset_scaling_flags_out() -> None:
    argv = libmaker_argv(Path("POPC.itp"), "PO4", {})
    assert argv == ["TS2CG", "libmaker", "-p", "POPC.itp", "-b", "PO4", "-o", "lib.txt"]
