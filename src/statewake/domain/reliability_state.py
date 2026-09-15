"""Evidence-backed reliability-state lifecycle primitives."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from statewake.utils.json_support import JsonValue, string_sequence
from statewake.utils.time import parse_datetime

RELIABILITY_STATES = ("unknown", "reliable", "degraded", "unreliable", "recovered")

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "unknown": frozenset({"reliable", "degraded", "unreliable"}),
    "reliable": frozenset({"degraded", "unreliable"}),
    "degraded": frozenset({"reliable", "unreliable"}),
    "unreliable": frozenset({"recovered", "reliable", "degraded"}),
    "recovered": frozenset({"reliable", "degraded", "unreliable"}),
}


def _canonical(payload: Mapping[str, JsonValue]) -> bytes:
    """Return the canonical representation used for deterministic identity and signing."""
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(value: str, field: str) -> None:
    """Return the SHA-256 digest of the supplied canonical bytes."""
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field} must be lowercase SHA-256 hex.")


@dataclass(frozen=True, slots=True)
class ReliabilityStateTransition:
    """Immutable, hash-linked evidence of one reliability-state transition."""

    transition_id: str
    subject_id: str
    from_state: str
    to_state: str
    occurred_at: datetime
    actor: str
    evidence_chain_id: str
    evidence_chain_digest: str
    decision: str
    rationale: tuple[str, ...] = ()
    previous_transition_digest: str = ""
    digest: str = ""

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if (
            not self.transition_id.strip()
            or not self.subject_id.strip()
            or not self.actor.strip()
        ):
            raise ValueError("transition_id, subject_id, and actor must not be empty.")
        if self.from_state not in RELIABILITY_STATES:
            raise ValueError(f"unsupported from_state: {self.from_state}")
        if self.to_state not in RELIABILITY_STATES:
            raise ValueError(f"unsupported to_state: {self.to_state}")
        if self.to_state not in ALLOWED_TRANSITIONS.get(self.from_state, frozenset()):
            raise ValueError(
                f"invalid reliability-state transition: {self.from_state} -> {self.to_state}"
            )
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware.")
        if not self.evidence_chain_id.strip():
            raise ValueError("evidence_chain_id must not be empty.")
        _sha256(self.evidence_chain_digest, "evidence_chain_digest")
        if self.previous_transition_digest:
            _sha256(self.previous_transition_digest, "previous_transition_digest")
        if self.decision not in {"accept", "review", "reject"}:
            raise ValueError("decision must be accept, review, or reject.")
        if self.to_state in {"reliable", "recovered"} and self.decision != "accept":
            raise ValueError(
                "reliable/recovered transitions require an accept decision."
            )
        if self.to_state == "degraded" and self.decision != "review":
            raise ValueError("degraded transitions require a review decision.")
        if self.to_state == "unreliable" and self.decision != "reject":
            raise ValueError("unreliable transitions require a reject decision.")
        object.__setattr__(self, "occurred_at", self.occurred_at.astimezone(UTC))

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            "transition_id": self.transition_id,
            "subject_id": self.subject_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "occurred_at": self.occurred_at.isoformat(),
            "actor": self.actor,
            "evidence_chain_id": self.evidence_chain_id,
            "evidence_chain_digest": self.evidence_chain_digest,
            "decision": self.decision,
            "rationale": list(self.rationale),
            "previous_transition_digest": self.previous_transition_digest,
        }

    @property
    def computed_digest(self) -> str:
        """Digest computed from the canonical payload."""
        return sha256(_canonical(self.payload())).hexdigest()

    def to_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        payload = self.payload()
        if include_digest:
            payload["digest"] = self.computed_digest
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, JsonValue]) -> ReliabilityStateTransition:
        """Construct this object from its serialized dictionary representation."""
        supplied = str(payload.get("digest", ""))
        if supplied:
            unsigned = dict(payload)
            unsigned.pop("digest", None)
            expected = sha256(_canonical(unsigned)).hexdigest()
            if supplied != expected:
                raise ValueError("reliability-state transition digest mismatch.")
        item = cls(
            transition_id=str(payload["transition_id"]),
            subject_id=str(payload["subject_id"]),
            from_state=str(payload["from_state"]),
            to_state=str(payload["to_state"]),
            occurred_at=parse_datetime(
                str(payload["occurred_at"]), field="occurred_at"
            ),
            actor=str(payload["actor"]),
            evidence_chain_id=str(payload["evidence_chain_id"]),
            evidence_chain_digest=str(payload["evidence_chain_digest"]),
            decision=str(payload["decision"]),
            rationale=string_sequence(payload.get("rationale", []), field="rationale"),
            previous_transition_digest=str(
                payload.get("previous_transition_digest", "")
            ),
        )
        if supplied and supplied != item.computed_digest:
            raise ValueError("reliability-state transition digest mismatch.")
        return item


@dataclass(frozen=True, slots=True)
class ReliabilityStateSnapshot:
    """Current authoritative reliability state derived from verified transition history."""

    subject_id: str
    state: str
    transition_id: str | None
    transition_digest: str | None
    evidence_chain_id: str | None

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if not self.subject_id.strip():
            raise ValueError("subject_id must not be empty.")
        if self.state not in RELIABILITY_STATES:
            raise ValueError(f"unsupported state: {self.state}")
        if self.transition_digest is not None:
            _sha256(self.transition_digest, "transition_digest")

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {
            "subject_id": self.subject_id,
            "state": self.state,
            "transition_id": self.transition_id,
            "transition_digest": self.transition_digest,
            "evidence_chain_id": self.evidence_chain_id,
        }
