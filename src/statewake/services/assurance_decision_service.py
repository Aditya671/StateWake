"""Strict persisted assurance decision and operational-exception verification."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from statewake.domain.assurance_operations import (
    AssuranceDecision,
    AssuranceDecisionInput,
    AssuranceException,
    SecurityDecision,
    assurance_decision_from_dict,
    assurance_exception_from_dict,
    evaluate_assurance_decision,
)


def _read_json_object(path: Path, *, max_bytes: int) -> dict[str, Any]:
    """Read one bounded UTF-8 JSON object without following a symlink."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError("assurance artifact path cannot traverse a symlink")
    with path.open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise OverflowError("assurance artifact exceeds configured byte limit")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("assurance artifact must be UTF-8") from exc
    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError("assurance artifact is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("assurance artifact must contain a JSON object")
    return payload


def load_assurance_decision(path: Path, *, max_bytes: int) -> AssuranceDecision:
    """Load and semantically verify one persisted assurance decision."""
    decision = assurance_decision_from_dict(
        _read_json_object(path, max_bytes=max_bytes)
    )
    verify_assurance_decision_semantics(decision)
    return decision


def load_assurance_exception(path: Path, *, max_bytes: int) -> AssuranceException:
    """Load one current or legacy persisted operational exception."""
    return assurance_exception_from_dict(_read_json_object(path, max_bytes=max_bytes))


def _rationale_value(decision: AssuranceDecision, prefix: str) -> str:
    """Return one canonical rationale value recorded by the policy evaluator."""
    matches = [
        item[len(prefix) :] for item in decision.rationale if item.startswith(prefix)
    ]
    if len(matches) != 1 or not matches[0].strip():
        raise ValueError(f"assurance decision is missing canonical rationale: {prefix}")
    return matches[0]


def verify_assurance_decision_semantics(decision: AssuranceDecision) -> None:
    """Replay the deterministic assurance policy and require an exact decision match."""
    trust_status = _rationale_value(decision, "trust-status:")
    rule = _rationale_value(decision, "policy-rule:")
    when = datetime.fromisoformat(decision.generated_at)
    if when.tzinfo is None:
        raise ValueError("assurance decision timestamp must be timezone-aware")
    replayed = evaluate_assurance_decision(
        AssuranceDecisionInput(
            subject_id=decision.subject_id,
            reliability_state=decision.source_reliability_state,
            verification_status=decision.source_verification_status,
            trust_status=trust_status,
            recovery_required=rule == "recovery-required",
            evidence_references=decision.evidence_references,
            verification_results=decision.verification_results,
            residual_risk=decision.residual_risk,
        ),
        policy_id=decision.policy_id,
        policy_version=decision.policy_version,
        generated_at=when.astimezone(UTC),
    )
    if replayed.to_dict() != decision.to_dict():
        raise ValueError(
            "assurance decision does not match deterministic policy replay"
        )


def verify_assurance_exception_binding(
    decision: AssuranceDecision,
    exception: AssuranceException,
    *,
    evaluated_at: datetime,
) -> str:
    """Verify exception-to-decision binding and return active/expired status."""
    if evaluated_at.tzinfo is None:
        raise ValueError("exception evaluation timestamp must be timezone-aware")
    if decision.decision not in {
        SecurityDecision.ALLOW_WITH_LIMITATIONS,
        SecurityDecision.REQUIRE_REVERIFICATION,
    }:
        raise ValueError("recorded decision does not permit an operational exception")
    if exception.subject_id != decision.subject_id:
        raise ValueError("assurance exception subject does not match decision")
    if exception.invariant != f"decision:{decision.decision.value}":
        raise ValueError("assurance exception invariant does not match decision")
    if exception.evidence_references != decision.evidence_references:
        raise ValueError(
            "assurance exception evidence references do not match decision"
        )
    if (
        exception.decision_digest is not None
        and exception.decision_digest != decision.digest
    ):
        raise ValueError("assurance exception decision digest does not match decision")
    expires = datetime.fromisoformat(exception.expires_at)
    if expires.tzinfo is None:
        raise ValueError("assurance exception expiry must be timezone-aware")
    return (
        "active"
        if evaluated_at.astimezone(UTC) < expires.astimezone(UTC)
        else "expired"
    )


def assurance_artifact_bytes(path: Path, *, max_bytes: int) -> int:
    """Return the bounded byte length of one configured assurance artifact."""
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError("assurance artifact path cannot traverse a symlink")
    with path.open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise OverflowError("assurance artifact exceeds configured byte limit")
    return len(raw)
