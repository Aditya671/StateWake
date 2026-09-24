"""Fault-specific study validators do not borrow generic profile rejection."""

from __future__ import annotations

import pytest

from statewake.validation_study.metrics import (
    _provenance_edge_check,
    _reliability_transition_check,
    run_validation_case,
)


@pytest.mark.parametrize(
    "fault", ("broken_provenance_edge", "invalid_reliability_transition")
)
def test_fault_is_detected_by_its_own_validator(fault: str) -> None:
    observed = run_validation_case("tool_action", "statewake_full", (fault,))
    assert observed.injected_faults == (fault,)
    assert observed.detected_faults == (fault,)
    assert observed.profile_satisfied is True  # no generic failed chain is substituted


def test_provenance_edge_positive_and_negative_controls() -> None:
    assert _provenance_edge_check(broken=False) is False
    assert _provenance_edge_check(broken=True) is True


def test_reliability_transition_positive_and_negative_controls() -> None:
    assert _reliability_transition_check(invalid=False) is False
    assert _reliability_transition_check(invalid=True) is True


def test_other_baselines_do_not_claim_untested_detection() -> None:
    for fault in ("broken_provenance_edge", "invalid_reliability_transition"):
        for baseline in ("final_output_only", "conventional_logs", "structured_traces"):
            result = run_validation_case("tool_action", baseline, (fault,))
            assert result.detected_faults == ()
            assert result.profile_satisfied is None
