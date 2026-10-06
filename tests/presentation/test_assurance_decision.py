"""Regression coverage for assurance decision/exception presentation recovery."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from statewake.domain.assurance_operations import (
    AssuranceDecisionInput,
    AssuranceException,
    create_assurance_exception,
    evaluate_assurance_decision,
)
from statewake.presentation.assurance_decision import AssuranceDecisionProjection
from statewake.services.assurance_decision_service import (
    verify_assurance_decision_semantics,
)

NOW = datetime(2026, 9, 30, tzinfo=UTC)


def _decision():
    return evaluate_assurance_decision(
        AssuranceDecisionInput(
            subject_id="subject-secret",
            reliability_state="degraded",
            verification_status="verified",
            trust_status="trusted",
            evidence_references=("evidence-secret",),
            verification_results=("verified",),
            residual_risk=("manual review remains",),
        ),
        generated_at=NOW,
    )


def test_decision_semantic_replay_and_exact_exception_binding() -> None:
    decision = _decision()
    verify_assurance_decision_semantics(decision)
    exception = create_assurance_exception(
        decision,
        exception_id="exception-secret",
        reason_operation_continues="bounded continuation",
        authorized_by="authorizer-secret",
        expires_at=NOW + timedelta(hours=1),
        compensating_control="manual verification",
        reverification_required="before expiry",
        created_at=NOW,
    )
    payload = AssuranceDecisionProjection(decision, exception, NOW).to_dict()
    assert payload["exception"]["binding"] == "exact-decision-digest"  # type: ignore[index]
    assert payload["exception"]["status"] == "active"  # type: ignore[index]
    assert "subject-secret" not in repr(payload)
    assert "authorizer-secret" not in repr(payload)


def test_legacy_exception_remains_explicitly_unbound() -> None:
    decision = _decision()
    modern = create_assurance_exception(
        decision,
        exception_id="exc",
        reason_operation_continues="bounded continuation",
        authorized_by="owner",
        expires_at=NOW + timedelta(hours=1),
        compensating_control="manual verification",
        reverification_required="before expiry",
        created_at=NOW,
    )
    legacy = AssuranceException(
        exception_id=modern.exception_id,
        subject_id=modern.subject_id,
        invariant=modern.invariant,
        reason_operation_continues=modern.reason_operation_continues,
        authorized_by=modern.authorized_by,
        expires_at=modern.expires_at,
        compensating_control=modern.compensating_control,
        reverification_required=modern.reverification_required,
        evidence_references=modern.evidence_references,
        created_at=modern.created_at,
    )
    payload = AssuranceDecisionProjection(decision, legacy, NOW).to_dict()
    assert payload["exception"]["binding"] == "legacy-unbound"  # type: ignore[index]
