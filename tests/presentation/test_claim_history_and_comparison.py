"""Regression tests for recorded history and two-report comparison projections."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from statewake.domain.reliability_state import ReliabilityStateTransition
from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.presentation import (
    ReportSourceContext,
    build_claim_comparison,
    build_claim_history,
)


def _mapping(value: object) -> dict[str, object]:
    """Narrow one JSON-like projection object for type-safe assertions."""
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _mapping_list(value: object) -> list[dict[str, object]]:
    """Narrow one JSON-like projection list for type-safe assertions."""
    assert isinstance(value, list)
    return cast(list[dict[str, object]], value)


def _report(**changes: object) -> ReliabilityVerificationReport:
    values: dict[str, object] = {
        "format_version": "1",
        "claim": "RAG answer verified",
        "decision": "review",
        "profile_id": "rag_answer_verified.v1",
        "profile_version": "1",
        "verified": False,
        "evidence_included": ("run",),
        "evidence_omitted": (),
        "evidence_missing": ("retrieval",),
        "checks_passed": ("chain",),
        "checks_failed": ("retrieval",),
        "checks_unrun": (),
        "checks_unknown": (),
        "source_identities": ("run-1",),
        "artifact_digests": ("a" * 64,),
        "rationale": ("review required",),
        "caveats": ("bounded",),
        "residual_risks": ("external correctness",),
        "human_decisions_required": ("Reviewer decision",),
        "allowed_use": ("inspection",),
        "prohibited_use": ("automatic approval",),
        "machine_readable_appendix": (),
        "recovery_status": "pending",
        "verifier_version": "statewake-test",
        "generated_at": "2026-09-27T00:00:00+00:00",
        "candidate_identity": "chain-1",
        "candidate_digest": "b" * 64,
        "report_type": "engineering",
        "profile_evaluation_digest": "c" * 64,
        "approval_status": "requires-human-approval",
    }
    values.update(changes)
    return ReliabilityVerificationReport(**values)  # type: ignore[arg-type]


def _source(record_id: str) -> ReportSourceContext:
    return ReportSourceContext(
        record_id=record_id,
        artifact_digest="d" * 64,
        producer_id="statewake.test",
        producer_type="statewake-verification-report",
        captured_at="2026-09-27T00:00:00+00:00",
    )


def _transition(
    *,
    chain_id: str = "chain-1",
    chain_digest: str = "b" * 64,
) -> ReliabilityStateTransition:
    return ReliabilityStateTransition(
        transition_id="transition-1",
        subject_id="agent-1",
        from_state="unknown",
        to_state="degraded",
        occurred_at=datetime(2026, 9, 27, tzinfo=UTC),
        actor="engine",
        evidence_chain_id=chain_id,
        evidence_chain_digest=chain_digest,
        decision="review",
        rationale=("review required",),
    )


def test_claim_history_includes_only_exact_candidate_binding() -> None:
    report = _report()
    unrelated = _transition(chain_id="chain-other", chain_digest="e" * 64)
    history = build_claim_history(
        "f" * 64,
        report,
        (unrelated, _transition()),
        max_items=10,
    ).to_dict()
    items = _mapping_list(history["items"])
    assert history["recorded_count"] == 1
    assert items[0]["evidence_chain_id"] == report.candidate_identity
    assert items[0]["evidence_chain_digest"] == report.candidate_digest


def test_claim_history_rejects_same_identity_with_different_digest() -> None:
    with pytest.raises(ValueError, match="candidate digest conflicts"):
        build_claim_history(
            "f" * 64,
            _report(),
            (_transition(chain_digest="e" * 64),),
            max_items=10,
        )


def test_claim_history_enforces_item_bound() -> None:
    first = _transition()
    second = ReliabilityStateTransition(
        transition_id="transition-2",
        subject_id="agent-2",
        from_state="unknown",
        to_state="degraded",
        occurred_at=datetime(2026, 9, 27, 1, tzinfo=UTC),
        actor="engine",
        evidence_chain_id="chain-1",
        evidence_chain_digest="b" * 64,
        decision="review",
    )
    with pytest.raises(OverflowError, match="item limit"):
        build_claim_history("f" * 64, _report(), (first, second), max_items=1)


def test_comparison_shows_field_deltas_without_assigning_severity() -> None:
    left = _report()
    right = _report(
        decision="accept",
        verified=True,
        evidence_missing=(),
        checks_failed=(),
        checks_passed=("chain", "retrieval"),
        candidate_digest="e" * 64,
        approval_status="not-approval",
        human_decisions_required=(),
        residual_risks=(),
    )
    result = build_claim_comparison(
        left,
        _source("1" * 64),
        right,
        _source("2" * 64),
    ).to_dict()
    changes = _mapping(result["changes"])
    decision_change = _mapping(changes["decision"])
    checks = _mapping(changes["checks"])
    passed_changes = _mapping(checks["passed"])
    assert result["semantic_scope_same"] is True
    assert changes["candidate_digest_changed"] is True
    assert decision_change == {
        "before": "review",
        "after": "accept",
        "changed": True,
    }
    assert passed_changes["added"] == ["retrieval"]
    assert "severity" not in changes


def test_comparison_marks_profile_version_mismatch_as_non_equivalent() -> None:
    result = build_claim_comparison(
        _report(),
        _source("1" * 64),
        _report(profile_version="2"),
        _source("2" * 64),
    ).to_dict()
    assert result["semantic_scope_same"] is False
    assert result["non_equivalence_warnings"] == ["profile-version-differs"]
