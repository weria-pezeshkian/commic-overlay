"""Parsing tqdm's own default progress-bar text out of a CALM subprocess's combined output.

CALM's own per-frame fitting loops (e.g. `analyze/lipids.py`'s `for future
in tqdm(futures)`) already report progress this way on their own - this
reads that existing output instead of CALM needing to expose anything new
for the overlay specifically. Confirmed directly against a real `tqdm`
run: `'\\rfitting surfaces:   0%|          | 0/3 [00:00<?, ?it/s]\\r...'`
- an optional `desc: ` prefix, `NNN%`, a `|...|` bar (whatever fill
character tqdm picked - never assumed, just skipped over), then
`current/total`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_TQDM_PATTERN = re.compile(
    r"(?:(?P<desc>[^\r\n:]+):\s*)?(?P<percent>\d{1,3})%\|[^|]*\|\s*(?P<current>\d+)/(?P<total>\d+)"
)


@dataclass(frozen=True)
class ProgressState:
    description: str | None
    percent: int
    current: int
    total: int


def parse_latest_progress(text: str) -> ProgressState | None:
    """The LAST tqdm-style progress update found in `text`, or None if there isn't one.

    tqdm redraws its own bar in place via carriage returns, so a single
    chunk of subprocess output can contain many already-superseded
    updates - only the most recent one is worth showing.
    """
    latest = None
    for match in _TQDM_PATTERN.finditer(text):
        latest = match
    if latest is None:
        return None
    return ProgressState(
        description=latest.group("desc"),
        percent=int(latest.group("percent")),
        current=int(latest.group("current")),
        total=int(latest.group("total")),
    )
