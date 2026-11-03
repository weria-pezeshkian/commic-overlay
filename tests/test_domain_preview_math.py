"""Tests for ts2cg_bridge/domain_preview_math.py - stubbed callables, no real TS2CG call."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from commic_overlay.ts2cg.state import DomainOp, DopSpec, WizardState
from commic_overlay.ts2cg.ts2cg_bridge.domain_preview_math import (
    PreviewDomains,
    compute_preview_domains,
    domain_point_shares,
    undefined_domain_count,
)


class _FakeLeaflet:
    def __init__(self, n: int) -> None:
        self.domain_ids = np.zeros(n, dtype=int)


class _FakeMembrane:
    def __init__(self, n: int = 10, monolayer: bool = False) -> None:
        self.outer = _FakeLeaflet(n)
        self.monolayer = monolayer
        self.inner = None if monolayer else _FakeLeaflet(n)


class _RecordingAssignDomains:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def __call__(self, membrane: object, *arguments: object) -> None:
        self.calls.append(arguments)


class _RecordingApplyOp:
    def __init__(self) -> None:
        self.domain_ids: list[int] = []

    def __call__(self, membrane: object, op: DomainOp) -> None:
        self.domain_ids.append(op.domain_id)


def _spec_tuple(domain_id: int, percentage: float, curvature: float) -> tuple[object, ...]:
    return (domain_id, percentage, curvature)


def test_compute_preview_domains_skips_assign_domains_without_dop_specs(tmp_path: Path) -> None:
    membrane = _FakeMembrane()
    assign_domains = _RecordingAssignDomains()
    result = compute_preview_domains(
        tmp_path, WizardState(), [], load=lambda _path: membrane, assign_domains=assign_domains,
    )
    assert assign_domains.calls == []
    assert np.array_equal(result.outer, membrane.outer.domain_ids)
    assert result.inner is not None


def test_compute_preview_domains_calls_assign_domains_with_dop_specs(tmp_path: Path) -> None:
    state = WizardState()
    state.dop_specs = [DopSpec(domain_id=0, percentage=1.0)]
    state.dop_leaflet = "outer"
    state.dop_k_factor = 3.0
    assign_domains = _RecordingAssignDomains()
    compute_preview_domains(
        tmp_path, state, [], load=lambda _path: _FakeMembrane(), assign_domains=assign_domains, lipid_spec=_spec_tuple,
    )
    assert assign_domains.calls == [([(0, 1.0, 0.0)], "outer", 3.0, False, None)]


def test_compute_preview_domains_replays_the_given_ops_in_order_skipping_exclusions(tmp_path: Path) -> None:
    ops = [
        DomainOp(kind="dai_point", domain_id=1, point_ids=[0]),
        DomainOp(kind="exclusion", point_ids=[1]),
        DomainOp(kind="dai_inclusion", domain_id=2, protein_type_id=1),
    ]
    apply_op = _RecordingApplyOp()
    compute_preview_domains(tmp_path, WizardState(), ops, load=lambda _path: _FakeMembrane(), apply_op=apply_op)
    assert apply_op.domain_ids == [1, 2]


def test_compute_preview_domains_replays_only_the_ops_it_is_given(tmp_path: Path) -> None:
    state = WizardState()
    state.domain_ops = [DomainOp(kind="dai_point", domain_id=1, point_ids=[0])]
    apply_op = _RecordingApplyOp()
    compute_preview_domains(tmp_path, state, [], load=lambda _path: _FakeMembrane(), apply_op=apply_op)
    assert apply_op.domain_ids == []


def test_compute_preview_domains_monolayer_has_no_inner(tmp_path: Path) -> None:
    result = compute_preview_domains(tmp_path, WizardState(), [], load=lambda _path: _FakeMembrane(monolayer=True))
    assert result.inner is None


def test_undefined_domain_count_counts_missing_domain_ids() -> None:
    domains = PreviewDomains(outer=np.array([0, 0, 1, 1, 1]), inner=np.array([0, 0, 0, 0, 0]))
    assert undefined_domain_count(domains, domain_count=4) == 2


def test_undefined_domain_count_counts_a_domain_present_on_one_leaflet_as_defined() -> None:
    domains = PreviewDomains(outer=np.array([0, 0]), inner=np.array([0, 1]))
    assert undefined_domain_count(domains, domain_count=2) == 0


def test_undefined_domain_count_zero_when_every_domain_present() -> None:
    domains = PreviewDomains(outer=np.array([0, 1]), inner=None)
    assert undefined_domain_count(domains, domain_count=2) == 0


def test_domain_point_shares_lists_only_domains_with_points() -> None:
    domains = PreviewDomains(outer=np.array([0, 0, 0, 2]), inner=np.array([0, 2, 2, 2]))
    assert domain_point_shares(domains) == {0: (0.75, 0.25), 2: (0.25, 0.75)}


def test_domain_point_shares_of_a_monolayer_has_no_inner_share() -> None:
    domains = PreviewDomains(outer=np.array([1, 1]), inner=None)
    assert domain_point_shares(domains) == {1: (1.0, None)}
