"""Read-only assurance-decision and operational-exception investigation projection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from statewake.domain.assurance_operations import AssuranceDecision, AssuranceException
from statewake.services.assurance_decision_service import (
    verify_assurance_exception_binding,
)

ASSURANCE_DECISION_SCHEMA_VERSION = "assurance-decision-investigation.v1"


def _digest_text(value: str) -> str:
    """Return a stable privacy-safe identity digest."""
    return sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AssuranceDecisionProjection:
    """Privacy-safe read projection over one decision and optional exception."""

    decision: AssuranceDecision
    exception: AssuranceException | None = None
    evaluated_at: datetime | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the deterministic operator investigation contract."""
        when = self.evaluated_at or datetime.now(UTC)
        if when.tzinfo is None:
            raise ValueError("evaluation timestamp must be timezone-aware")
        exception_payload: dict[str, object]
        if self.exception is None:
            exception_payload = {"present": False}
        else:
            status = verify_assurance_exception_binding(
                self.decision,
                self.exception,
                evaluated_at=when,
            )
            exception_payload = {
                "present": True,
                "exception_id_digest": _digest_text(self.exception.exception_id),
                "binding": (
                    "exact-decision-digest"
                    if self.exception.decision_digest is not None
                    else "legacy-unbound"
                ),
                "decision_digest": self.exception.decision_digest,
                "status": status,
                "created_at": self.exception.created_at,
                "expires_at": self.exception.expires_at,
                "authorized_by_digest": _digest_text(self.exception.authorized_by),
                "compensating_control": self.exception.compensating_control,
                "reverification_required": self.exception.reverification_required,
                "evidence_reference_digests": [
                    _digest_text(item) for item in self.exception.evidence_references
                ],
                "system_state_preserved": self.exception.system_state_preserved,
            }
        rule = next(
            (
                item.split(":", 1)[1]
                for item in self.decision.rationale
                if item.startswith("policy-rule:")
            ),
            "unknown",
        )
        return {
            "schema_version": ASSURANCE_DECISION_SCHEMA_VERSION,
            "decision": {
                "decision": self.decision.decision.value,
                "digest": self.decision.digest,
                "subject_id_digest": _digest_text(self.decision.subject_id),
                "policy_id": self.decision.policy_id,
                "policy_version": self.decision.policy_version,
                "policy_rule": rule,
                "generated_at": self.decision.generated_at,
                "source_reliability_state": self.decision.source_reliability_state,
                "source_verification_status": self.decision.source_verification_status,
                "evidence_reference_digests": [
                    _digest_text(item) for item in self.decision.evidence_references
                ],
                "verification_results": list(self.decision.verification_results),
                "residual_risk": list(self.decision.residual_risk),
                "system_state_unchanged": self.decision.system_state_unchanged,
                "semantic_replay_verified": True,
                "rationale_exposed": False,
            },
            "exception": exception_payload,
            "authorization": {
                "factual_correctness_evaluated": False,
                "publication_authorized": False,
                "compliance_certified": False,
                "host_authorization_inferred": False,
            },
            "limitations": [
                "The configured JSON files are explicit read inputs, not a canonical StateWake decision-history store.",
                "An operational exception never rewrites the underlying assurance state.",
                "Legacy exception records without decision_digest cannot prove exact decision binding.",
                "This view does not establish factual correctness, publication permission, compliance, or host authorization.",
            ],
        }
