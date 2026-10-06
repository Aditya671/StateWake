"""Deterministic assurance decisions and bounded operational exceptions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any


class SecurityDecision(StrEnum):
    """Bounded security-assurance outcomes owned by StateWake."""

    ALLOW = "ALLOW"
    ALLOW_WITH_LIMITATIONS = "ALLOW_WITH_LIMITATIONS"
    REQUIRE_REVERIFICATION = "REQUIRE_REVERIFICATION"
    QUARANTINE = "QUARANTINE"
    REJECT = "REJECT"
    REVOKE_TRUST = "REVOKE_TRUST"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"


_ALLOWED_VERIFICATION = {
    "verified",
    "verified_with_limitations",
    "unverified",
    "invalid",
    "tampered",
    "incomplete",
    "trust_anchor_unavailable",
}
_ALLOWED_STATES = {"unknown", "reliable", "degraded", "unreliable", "recovered"}


def _canonical(payload: Mapping[str, Any]) -> bytes:
    """Return the canonical bytes used for deterministic decision identity."""
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _timestamp(value: datetime) -> str:
    """Normalize one decision timestamp to canonical UTC ISO-8601 form."""
    if value.tzinfo is None:
        raise ValueError("decision timestamps must be timezone-aware.")
    return value.astimezone(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class AssuranceDecisionInput:
    """Evidence-backed state presented to the deterministic assurance policy."""

    subject_id: str
    reliability_state: str
    verification_status: str
    trust_status: str = "trusted"
    recovery_required: bool = False
    evidence_references: tuple[str, ...] = ()
    verification_results: tuple[str, ...] = ()
    residual_risk: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate the decision input boundary."""
        if not self.subject_id.strip():
            raise ValueError("subject_id must not be empty.")
        if self.reliability_state not in _ALLOWED_STATES:
            raise ValueError(f"unsupported reliability state: {self.reliability_state}")
        if self.verification_status not in _ALLOWED_VERIFICATION:
            raise ValueError(
                f"unsupported verification status: {self.verification_status}"
            )
        if not self.trust_status.strip():
            raise ValueError("trust_status must not be empty.")
        if not self.evidence_references:
            raise ValueError("at least one evidence reference is required.")
        if any(not item.strip() for item in self.evidence_references):
            raise ValueError("evidence references must not be blank.")
        if any(not item.strip() for item in self.verification_results):
            raise ValueError("verification results must not be blank.")
        if any(not item.strip() for item in self.residual_risk):
            raise ValueError("residual risk entries must not be blank.")


@dataclass(frozen=True, slots=True)
class AssuranceDecision:
    """Explainable deterministic assurance decision with evidence bindings."""

    decision: SecurityDecision
    subject_id: str
    policy_id: str
    policy_version: str
    evidence_references: tuple[str, ...]
    verification_results: tuple[str, ...]
    rationale: tuple[str, ...]
    decision_context: str
    residual_risk: tuple[str, ...]
    generated_at: str
    source_reliability_state: str
    source_verification_status: str
    system_state_unchanged: bool = True
    digest: str = ""

    def __post_init__(self) -> None:
        """Validate and bind the immutable decision record."""
        if not self.subject_id.strip():
            raise ValueError("subject_id must not be empty.")
        if not self.policy_id.strip() or not self.policy_version.strip():
            raise ValueError("policy identity must not be empty.")
        if not self.evidence_references:
            raise ValueError("decision requires evidence references.")
        if not self.verification_results:
            raise ValueError("decision requires verification results.")
        if not self.rationale:
            raise ValueError("decision rationale must not be empty.")
        if not self.decision_context.strip():
            raise ValueError("decision context must not be empty.")
        if not self.system_state_unchanged:
            raise ValueError("operational decision must not rewrite system state.")
        expected = self.computed_digest()
        if self.digest and self.digest != expected:
            raise ValueError("assurance decision digest mismatch.")
        object.__setattr__(self, "digest", expected)

    def payload(self) -> dict[str, Any]:
        """Return the canonical decision payload."""
        return {
            "decision": self.decision.value,
            "subject_id": self.subject_id,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "evidence_references": list(self.evidence_references),
            "verification_results": list(self.verification_results),
            "rationale": list(self.rationale),
            "decision_context": self.decision_context,
            "residual_risk": list(self.residual_risk),
            "generated_at": self.generated_at,
            "source_reliability_state": self.source_reliability_state,
            "source_verification_status": self.source_verification_status,
            "system_state_unchanged": self.system_state_unchanged,
        }

    def computed_digest(self) -> str:
        """Return the deterministic digest of this decision."""
        return sha256(_canonical(self.payload())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the decision without losing its evidence rationale."""
        return {**self.payload(), "digest": self.digest}


@dataclass(frozen=True, slots=True)
class AssuranceException:
    """Evidence-backed operating exception that never changes system assurance state."""

    exception_id: str
    subject_id: str
    invariant: str
    reason_operation_continues: str
    authorized_by: str
    expires_at: str
    compensating_control: str
    reverification_required: str
    evidence_references: tuple[str, ...]
    created_at: str
    decision_digest: str | None = None
    system_state_preserved: bool = True
    digest: str = ""

    def __post_init__(self) -> None:
        """Validate the exception boundary and bind its identity."""
        for name in (
            "exception_id",
            "subject_id",
            "invariant",
            "reason_operation_continues",
            "authorized_by",
            "expires_at",
            "compensating_control",
            "reverification_required",
            "created_at",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        if not self.evidence_references:
            raise ValueError("exception requires evidence references.")
        created = datetime.fromisoformat(self.created_at)
        expires = datetime.fromisoformat(self.expires_at)
        if created.tzinfo is None or expires.tzinfo is None:
            raise ValueError("exception timestamps must be timezone-aware.")
        if expires.astimezone(UTC) <= created.astimezone(UTC):
            raise ValueError("exception expiry must be later than creation.")
        if self.decision_digest is not None:
            if len(self.decision_digest) != 64 or any(
                ch not in "0123456789abcdef" for ch in self.decision_digest
            ):
                raise ValueError("decision_digest must be a lowercase sha256 digest.")
        if not self.system_state_preserved:
            raise ValueError("exception must preserve system assurance state.")
        expected = self.computed_digest()
        if self.digest and self.digest != expected:
            raise ValueError("assurance exception digest mismatch.")
        object.__setattr__(self, "digest", expected)

    def payload(self) -> dict[str, Any]:
        """Return the canonical exception payload."""
        return {
            "exception_id": self.exception_id,
            "subject_id": self.subject_id,
            "invariant": self.invariant,
            "reason_operation_continues": self.reason_operation_continues,
            "authorized_by": self.authorized_by,
            "expires_at": self.expires_at,
            "compensating_control": self.compensating_control,
            "reverification_required": self.reverification_required,
            "evidence_references": list(self.evidence_references),
            "created_at": self.created_at,
            **(
                {"decision_digest": self.decision_digest}
                if self.decision_digest is not None
                else {}
            ),
            "system_state_preserved": self.system_state_preserved,
        }

    def computed_digest(self) -> str:
        """Return the deterministic digest of the exception."""
        return sha256(_canonical(self.payload())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the exception record."""
        return {**self.payload(), "digest": self.digest}


def evaluate_assurance_decision(
    inputs: AssuranceDecisionInput,
    *,
    policy_id: str = "statewake-security-assurance",
    policy_version: str = "1",
    generated_at: datetime | None = None,
) -> AssuranceDecision:
    """Map verified StateWake evidence to one bounded operational decision."""
    if not policy_id.strip() or not policy_version.strip():
        raise ValueError("policy identity must not be empty.")
    when = _timestamp(generated_at or datetime.now(UTC))

    if inputs.trust_status == "revoked":
        decision = SecurityDecision.REVOKE_TRUST
        rule = "trust-authority-revoked"
    elif inputs.recovery_required:
        decision = SecurityDecision.RECOVERY_REQUIRED
        rule = "recovery-required"
    elif inputs.verification_status == "tampered":
        decision = SecurityDecision.QUARANTINE
        rule = "portable-evidence-tampered"
    elif inputs.verification_status in {"invalid", "incomplete"}:
        decision = SecurityDecision.REJECT
        rule = "evidence-invalid-or-incomplete"
    elif inputs.verification_status in {"unverified", "trust_anchor_unavailable"}:
        decision = SecurityDecision.REQUIRE_REVERIFICATION
        rule = "verification-not-established"
    elif inputs.reliability_state == "unreliable":
        decision = SecurityDecision.REJECT
        rule = "reliability-unacceptable"
    elif inputs.reliability_state == "degraded":
        decision = SecurityDecision.ALLOW_WITH_LIMITATIONS
        rule = "reliability-degraded"
    elif inputs.verification_status == "verified_with_limitations":
        decision = SecurityDecision.ALLOW_WITH_LIMITATIONS
        rule = "verification-limitations-present"
    elif inputs.reliability_state in {"reliable", "recovered"}:
        decision = SecurityDecision.ALLOW
        rule = "verified-reliability-state"
    else:
        decision = SecurityDecision.REQUIRE_REVERIFICATION
        rule = "state-not-sufficiently-established"

    rationale = (
        f"policy-rule:{rule}",
        f"reliability-state:{inputs.reliability_state}",
        f"verification-status:{inputs.verification_status}",
        f"trust-status:{inputs.trust_status}",
    )
    residual = inputs.residual_risk or (
        () if decision == SecurityDecision.ALLOW else (rule,)
    )
    return AssuranceDecision(
        decision=decision,
        subject_id=inputs.subject_id,
        policy_id=policy_id,
        policy_version=policy_version,
        evidence_references=inputs.evidence_references,
        verification_results=inputs.verification_results,
        rationale=rationale,
        decision_context="evidence-backed assurance policy evaluation",
        residual_risk=residual,
        generated_at=when,
        source_reliability_state=inputs.reliability_state,
        source_verification_status=inputs.verification_status,
    )


def create_assurance_exception(
    decision: AssuranceDecision,
    *,
    exception_id: str,
    reason_operation_continues: str,
    authorized_by: str,
    expires_at: datetime,
    compensating_control: str,
    reverification_required: str,
    created_at: datetime | None = None,
) -> AssuranceException:
    """Create an expiring, evidence-backed operating exception without changing state."""
    if decision.decision not in {
        SecurityDecision.ALLOW_WITH_LIMITATIONS,
        SecurityDecision.REQUIRE_REVERIFICATION,
    }:
        raise ValueError(
            "operating exceptions are limited to non-clear assurance decisions."
        )
    return AssuranceException(
        exception_id=exception_id,
        subject_id=decision.subject_id,
        invariant=f"decision:{decision.decision.value}",
        reason_operation_continues=reason_operation_continues,
        authorized_by=authorized_by,
        expires_at=_timestamp(expires_at),
        compensating_control=compensating_control,
        reverification_required=reverification_required,
        evidence_references=decision.evidence_references,
        created_at=_timestamp(created_at or datetime.now(UTC)),
        decision_digest=decision.digest,
    )


def _strict_string(value: Any, name: str) -> str:
    """Return one string without scalar coercion."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    return value


def _strict_bool(value: Any, name: str) -> bool:
    """Return one boolean without integer/string coercion."""
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean.")
    return value


def _strict_string_tuple(
    value: Any, name: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    """Return a strictly typed tuple of non-empty strings."""
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{name} must be an array of non-empty strings.")
    if not allow_empty and not value:
        raise ValueError(f"{name} must not be empty.")
    return tuple(value)


def _require_keys(
    payload: Mapping[str, Any], allowed: set[str], required: set[str], name: str
) -> None:
    """Reject unsupported or missing persisted fields."""
    extra = set(payload) - allowed
    missing = required - set(payload)
    if extra:
        raise ValueError(f"{name} contains unsupported fields: {sorted(extra)!r}")
    if missing:
        raise ValueError(f"{name} is missing required fields: {sorted(missing)!r}")


def assurance_decision_from_dict(payload: Mapping[str, Any]) -> AssuranceDecision:
    """Load one persisted assurance decision with strict scalar typing."""
    allowed = {
        "decision",
        "subject_id",
        "policy_id",
        "policy_version",
        "evidence_references",
        "verification_results",
        "rationale",
        "decision_context",
        "residual_risk",
        "generated_at",
        "source_reliability_state",
        "source_verification_status",
        "system_state_unchanged",
        "digest",
    }
    _require_keys(payload, allowed, allowed, "assurance decision")
    generated_at = _strict_string(payload["generated_at"], "generated_at")
    when = datetime.fromisoformat(generated_at)
    if when.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware.")
    decision_text = _strict_string(payload["decision"], "decision")
    try:
        decision = SecurityDecision(decision_text)
    except ValueError as exc:
        raise ValueError("unsupported assurance decision") from exc
    return AssuranceDecision(
        decision=decision,
        subject_id=_strict_string(payload["subject_id"], "subject_id"),
        policy_id=_strict_string(payload["policy_id"], "policy_id"),
        policy_version=_strict_string(payload["policy_version"], "policy_version"),
        evidence_references=_strict_string_tuple(
            payload["evidence_references"], "evidence_references", allow_empty=False
        ),
        verification_results=_strict_string_tuple(
            payload["verification_results"], "verification_results", allow_empty=False
        ),
        rationale=_strict_string_tuple(
            payload["rationale"], "rationale", allow_empty=False
        ),
        decision_context=_strict_string(
            payload["decision_context"], "decision_context"
        ),
        residual_risk=_strict_string_tuple(payload["residual_risk"], "residual_risk"),
        generated_at=generated_at,
        source_reliability_state=_strict_string(
            payload["source_reliability_state"], "source_reliability_state"
        ),
        source_verification_status=_strict_string(
            payload["source_verification_status"], "source_verification_status"
        ),
        system_state_unchanged=_strict_bool(
            payload["system_state_unchanged"], "system_state_unchanged"
        ),
        digest=_strict_string(payload["digest"], "digest"),
    )


def assurance_exception_from_dict(payload: Mapping[str, Any]) -> AssuranceException:
    """Load one current or legacy persisted operational exception strictly."""
    required = {
        "exception_id",
        "subject_id",
        "invariant",
        "reason_operation_continues",
        "authorized_by",
        "expires_at",
        "compensating_control",
        "reverification_required",
        "evidence_references",
        "created_at",
        "system_state_preserved",
        "digest",
    }
    allowed = required | {"decision_digest"}
    _require_keys(payload, allowed, required, "assurance exception")
    decision_digest = payload.get("decision_digest")
    if decision_digest is not None and not isinstance(decision_digest, str):
        raise ValueError("decision_digest must be a string when present.")
    return AssuranceException(
        exception_id=_strict_string(payload["exception_id"], "exception_id"),
        subject_id=_strict_string(payload["subject_id"], "subject_id"),
        invariant=_strict_string(payload["invariant"], "invariant"),
        reason_operation_continues=_strict_string(
            payload["reason_operation_continues"], "reason_operation_continues"
        ),
        authorized_by=_strict_string(payload["authorized_by"], "authorized_by"),
        expires_at=_strict_string(payload["expires_at"], "expires_at"),
        compensating_control=_strict_string(
            payload["compensating_control"], "compensating_control"
        ),
        reverification_required=_strict_string(
            payload["reverification_required"], "reverification_required"
        ),
        evidence_references=_strict_string_tuple(
            payload["evidence_references"], "evidence_references", allow_empty=False
        ),
        created_at=_strict_string(payload["created_at"], "created_at"),
        decision_digest=decision_digest,
        system_state_preserved=_strict_bool(
            payload["system_state_preserved"], "system_state_preserved"
        ),
        digest=_strict_string(payload["digest"], "digest"),
    )
