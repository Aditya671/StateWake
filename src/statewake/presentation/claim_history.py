"""Read-only history projection for one StateWake verification report candidate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256

from statewake.domain.reliability_state import ReliabilityStateTransition
from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)

HISTORY_SCHEMA_VERSION = "claim-history.v1"


@dataclass(frozen=True, slots=True)
class ClaimHistoryItem:
    """Represent one recorded reliability-state transition for the report candidate."""

    sequence: int
    transition: ReliabilityStateTransition

    def to_dict(self) -> dict[str, object]:
        """Return the stable history-item representation."""
        item = self.transition
        return {
            "sequence": self.sequence,
            "transition_id": item.transition_id,
            "subject_id": item.subject_id,
            "from_state": item.from_state,
            "to_state": item.to_state,
            "occurred_at": item.occurred_at.isoformat(),
            "actor": item.actor,
            "evidence_chain_id": item.evidence_chain_id,
            "evidence_chain_digest": item.evidence_chain_digest,
            "decision": item.decision,
            "rationale": list(item.rationale),
            "previous_transition_digest": item.previous_transition_digest,
            "transition_digest": item.computed_digest,
        }


@dataclass(frozen=True, slots=True)
class ClaimHistoryProjection:
    """Bounded recorded history linked by exact evidence-chain identity and digest."""

    report_record_id: str
    report: ReliabilityVerificationReport
    items: tuple[ClaimHistoryItem, ...]

    @property
    def digest(self) -> str:
        """Return a deterministic digest for the read-only history projection."""
        return sha256(
            json.dumps(
                self.to_dict(),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

    def to_dict(self) -> dict[str, object]:
        """Return the stable history projection representation."""
        return {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "report_record_id": self.report_record_id,
            "candidate": {
                "id": self.report.candidate_identity,
                "digest": self.report.candidate_digest,
            },
            "profile": {
                "id": self.report.profile_id,
                "version": self.report.profile_version,
            },
            "recorded_count": len(self.items),
            "items": [item.to_dict() for item in self.items],
            "limitations": [
                "This timeline contains only configured authoritative reliability-state "
                "history entries bound to this exact evidence-chain identity and digest.",
                "Absence of an entry does not prove that no external review or action occurred.",
            ],
        }


def build_claim_history(
    report_record_id: str,
    report: ReliabilityVerificationReport,
    transitions: tuple[ReliabilityStateTransition, ...],
    *,
    max_items: int,
) -> ClaimHistoryProjection:
    """Build history from validated transitions without synthesizing missing events."""
    if max_items < 1:
        raise ValueError("max_items must be positive")
    matches: list[ClaimHistoryItem] = []
    for transition in transitions:
        if transition.evidence_chain_id != report.candidate_identity:
            continue
        if transition.evidence_chain_digest != report.candidate_digest:
            raise ValueError(
                "reliability-state history candidate digest conflicts with report"
            )
        matches.append(ClaimHistoryItem(len(matches) + 1, transition))
        if len(matches) > max_items:
            raise OverflowError("claim history exceeds configured item limit")
    return ClaimHistoryProjection(
        report_record_id=report_record_id,
        report=report,
        items=tuple(matches),
    )


__all__ = [
    "ClaimHistoryItem",
    "ClaimHistoryProjection",
    "HISTORY_SCHEMA_VERSION",
    "build_claim_history",
]
