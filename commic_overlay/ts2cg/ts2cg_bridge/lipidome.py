"""Fetching and indexing the Martini 3 lipidome's own itp files.

TS2CG's own `libmaker` converts one lipid itp into a `.LIB` snippet, but
TS2CG itself ships no bundled, comprehensive lipid library covering this
- the Martini 3 Lipidome (M3-Lipid-Parameters) is the real, broad source
for that, so the overlay fetches it itself (plain HTTPS, no `git`
dependency) and indexes every lipid-category itp's own molecule names, so
the Select Lipids page can build its grouped checklist without running
`libmaker` on anything yet - that only happens, later, for whichever
lipids are actually selected (`libmaker_bridge.py`).
"""

from __future__ import annotations

import re
import shutil
import tarfile
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

LIPIDOME_ARCHIVE_URL = "https://github.com/Martini-Force-Field-Initiative/M3-Lipid-Parameters/archive/refs/heads/main.tar.gz"
LIPIDOME_DIRNAME = "M3-Lipid-Parameters"
ITP_SUBDIR = "ITPs"


def fetch_lipidome(cache_dir: Path, force: bool = False) -> Path:
    """Downloads (or reuses an already-cached) copy of the Martini 3 lipidome's own itp files.

    `cache_dir` holds one subdirectory, named `LIPIDOME_DIRNAME` - a
    second call against the same `cache_dir` is a no-op unless `force` is
    set, so relaunching the wizard doesn't re-download the archive every
    time. Returns `cache_dir / LIPIDOME_DIRNAME` - pass that to `itp_dir()`
    for the `ITPs/` path itself.
    """
    cache_dir = Path(cache_dir)
    target = cache_dir / LIPIDOME_DIRNAME
    if target.exists() and not force:
        return target

    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        archive_path = Path(tmp) / "lipidome.tar.gz"
        urllib.request.urlretrieve(LIPIDOME_ARCHIVE_URL, archive_path)  # noqa: S310 (fixed https URL)
        with tarfile.open(archive_path) as tar:
            tar.extractall(tmp, filter="data")  # noqa: S202 (archive is this overlay's own trusted fetch URL)
        # GitHub's own branch archive has one top-level directory (e.g.
        # "M3-Lipid-Parameters-main/") whose exact name tracks the branch,
        # not something to depend on - renamed to the stable LIPIDOME_DIRNAME
        # so repeated fetches always land in the same place regardless.
        extracted = next(p for p in Path(tmp).iterdir() if p.is_dir())
        if target.exists():
            shutil.rmtree(target)
        shutil.move(str(extracted), str(target))
    return target


def itp_dir(lipidome_dir: Path) -> Path:
    return Path(lipidome_dir) / ITP_SUBDIR


# The lipidome's own non-lipid itp files - confirmed against the real repo:
# "ffbonded" and the bare base-force-field file define no [moleculetype]
# blocks at all, but "ions"/"solvents" genuinely do (14 and 51
# [moleculetype]s respectively) - `read_itp_molecules` would happily parse
# real molecules out of those too, so they need an explicit exclusion
# rather than relying on "has no molecules" to filter them out.
_NON_LIPID_MARKERS = ("ffbonded", "_ions_", "_solvents_")
_BASE_FORCE_FIELD_RE = re.compile(r"^martini_v[\d.]+\.itp$", re.IGNORECASE)


def is_lipid_itp_filename(filename: str) -> bool:
    """False for the lipidome's own non-lipid itp files (see `_NON_LIPID_MARKERS` above)."""
    lowered = filename.lower()
    if _BASE_FORCE_FIELD_RE.match(lowered):
        return False
    return not any(marker in lowered for marker in _NON_LIPID_MARKERS)


_PREFIX_RE = re.compile(r"^martini_v[\d.]+_", re.IGNORECASE)
_SUFFIX_RE = re.compile(r"_v\d+$", re.IGNORECASE)


def group_label(itp_path: Path) -> str:
    """A readable group name for `itp_path`'s own filename stem.

    E.g. `martini_v3.0.0_phospholipids_PC_v2.itp` -> `phospholipids PC`.
    """
    stem = _PREFIX_RE.sub("", itp_path.stem)
    stem = _SUFFIX_RE.sub("", stem)
    return stem.replace("_", " ")


@dataclass(frozen=True)
class LipidomeIndex:
    """lipid name -> its source itp file, and itp file -> the lipid names found in it (in the
    order `read_itp_molecules` returned them - the order the Select Lipids page's own
    per-group checklist lists them in)."""

    lipid_to_itp: dict[str, Path] = field(default_factory=dict)
    itp_to_lipids: dict[Path, list[str]] = field(default_factory=dict)


def index_lipidome(itp_directory: Path) -> LipidomeIndex:
    """Parses every lipid-category itp file in `itp_directory` for its own molecule names.

    Cheap - just `[moleculetype]` headers, via TS2CG's own
    `read_itp_molecules` - no `libmaker` geometry step, so this can run
    once, synchronously, right when the Select Lipids page is first shown.
    """
    from TS2CG.core.itp_parser import read_itp_molecules  # deferred: see introspect.py's own note

    lipid_to_itp: dict[str, Path] = {}
    itp_to_lipids: dict[Path, list[str]] = {}
    for itp_path in sorted(Path(itp_directory).glob("*.itp")):
        if not is_lipid_itp_filename(itp_path.name):
            continue
        names = [mol.name for mol in read_itp_molecules(itp_path)]
        if not names:
            continue
        itp_to_lipids[itp_path] = names
        for name in names:
            lipid_to_itp[name] = itp_path
    return LipidomeIndex(lipid_to_itp=lipid_to_itp, itp_to_lipids=itp_to_lipids)
