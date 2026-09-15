"""Versioned, deterministic reliability claim profiles.

Claim profiles describe the minimum evidence and state conditions required for a
bounded reliability decision. They do not evaluate models or execute policy.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from statewake.utils.json_support import JsonValue, require_bool, string_sequence

_ALLOWED_DECISIONS = {"accept", "review", "reject"}
_ALLOWED_STATES = {"reliable", "degraded", "unreliable", "recovered"}
_ALLOWED_RECONCILIATION = {
    "pending",
    "verified",
    "stale",
    "missing",
    "invalid",
    "recovered",
}


def _canonical(payload: Mapping[str, JsonValue]) -> bytes:
    """Return the canonical representation used for comparison and hashing."""
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ReliabilityClaimProfile:
    """A versioned declaration of evidence/state requirements for one decision claim."""

    profile_id: str
    version: str
    title: str
    required_evidence_kinds: tuple[str, ...]
    required_verification_conditions: tuple[str, ...]
    allowed_decisions: tuple[str, ...]
    required_rationale: bool = True
    required_reconciliation_states: tuple[str, ...] = ()
    required_reliability_states: tuple[str, ...] = ()
    description: str = ""

    def __post_init__(self) -> None:
        """Validate and normalize the instance after initialization."""
        for name in ("profile_id", "version", "title"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        if not self.required_evidence_kinds:
            raise ValueError("required_evidence_kinds must not be empty.")
        if not self.allowed_decisions:
            raise ValueError("allowed_decisions must not be empty.")
        if any(item not in _ALLOWED_DECISIONS for item in self.allowed_decisions):
            raise ValueError("allowed_decisions contains unsupported decision.")
        if any(
            item not in _ALLOWED_RECONCILIATION
            for item in self.required_reconciliation_states
        ):
            raise ValueError(
                "required_reconciliation_states contains unsupported state."
            )
        if any(
            item not in _ALLOWED_STATES for item in self.required_reliability_states
        ):
            raise ValueError("required_reliability_states contains unsupported state.")
        if len(self.allowed_decisions) != len(set(self.allowed_decisions)):
            raise ValueError("allowed_decisions must not contain duplicates.")
        if len(self.required_evidence_kinds) != len(set(self.required_evidence_kinds)):
            raise ValueError("required_evidence_kinds must not contain duplicates.")

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            "profile_id": self.profile_id,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "required_evidence_kinds": list(self.required_evidence_kinds),
            "required_verification_conditions": list(
                self.required_verification_conditions
            ),
            "allowed_decisions": list(self.allowed_decisions),
            "required_rationale": self.required_rationale,
            "required_reconciliation_states": list(self.required_reconciliation_states),
            "required_reliability_states": list(self.required_reliability_states),
        }

    @property
    def digest(self) -> str:
        """Deterministic SHA-256 digest represented by this object."""
        return sha256(_canonical(self.payload())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to a dictionary."""
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_dict(cls, payload: Mapping[str, JsonValue]) -> ReliabilityClaimProfile:
        """Construct this object from its serialized dictionary representation."""
        result = cls(
            profile_id=str(payload["profile_id"]),
            version=str(payload["version"]),
            title=str(payload["title"]),
            description=str(payload.get("description", "")),
            required_evidence_kinds=string_sequence(
                payload.get("required_evidence_kinds", []),
                field="required_evidence_kinds",
            ),
            required_verification_conditions=string_sequence(
                payload.get("required_verification_conditions", []),
                field="required_verification_conditions",
            ),
            allowed_decisions=string_sequence(
                payload.get("allowed_decisions", []), field="allowed_decisions"
            ),
            required_rationale=require_bool(
                payload.get("required_rationale", True), field="required_rationale"
            ),
            required_reconciliation_states=string_sequence(
                payload.get("required_reconciliation_states", []),
                field="required_reconciliation_states",
            ),
            required_reliability_states=string_sequence(
                payload.get("required_reliability_states", []),
                field="required_reliability_states",
            ),
        )
        supplied = str(payload.get("digest", ""))
        if supplied and supplied != result.digest:
            raise ValueError("reliability claim profile digest mismatch.")
        return result
