"""Small, generic facts about the machine COMMIC Overlay is running on."""

from __future__ import annotations

import os


def default_worker_count(concurrent_jobs: int = 1) -> int:
    """A reasonable `--Workers` default for a CALM run, based on this machine's own CPU count.

    CALM's own CLI default is a conservative 1 (unparallelized) - a safe
    baseline for a bare `CALM` invocation with no idea what machine it's
    on, but needlessly slow for this overlay's own Run, which always has
    a specific machine's real core count available to it. Leaves one core
    free for the GUI itself (and the OS) rather than claiming every core.

    `concurrent_jobs` divides that budget evenly - when both `analyze
    full` and `analyze lipids` run at the same time
    (`calm_bridge/runner.py::ParallelCommandRunner`), each gets half the
    cores rather than each independently claiming (cpu_count - 1) and the
    two together oversubscribing the machine.
    """
    cpu_count = os.cpu_count() or 1
    available = max(1, cpu_count - 1)
    return max(1, available // max(1, concurrent_jobs))
