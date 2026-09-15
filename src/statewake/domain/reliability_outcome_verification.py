"""Deterministic end-to-end verification results for V1 reliability outcomes."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

_CHECKS = (
    "attestation_integrity",
    "evidence_chain_integrity",
    "evidence_sources",
    "state_transition_integrity",
    "state_transition_binding",
    "outcome_semantics",
    "comparison_binding",
    "reconciliation_binding",
    "recovery_outcome_binding",
    "attestation_binding",
)


def _canonical(payload: Mapping[str, Any]) -> bytes:
    """Return the canonical representation used for deterministic identity and signing."""
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ReliabilityOutcomeVerificationReport:
    """Inspectable, score-free verification outcome for one reliability attestation."""

    attestation_id: str
    subject_id: str
    verified: bool
    checks: tuple[str, ...]
    failures: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if not self.attestation_id.strip() or not self.subject_id.strip():
            raise ValueError("attestation_id and subject_id must not be empty.")
        if any(item not in _CHECKS for item in self.checks):
            raise ValueError("unsupported verification check.")
        if len(set(self.checks)) != len(self.checks):
            raise ValueError("verification checks must be unique.")
        if self.verified and self.failures:
            raise ValueError("verified report cannot contain failures.")
        if not self.verified and not self.failures:
            raise ValueError("unverified report must contain failures.")

    @property
    def digest(self) -> str:
        """Deterministic digest of this object."""
        return sha256(_canonical(self.to_dict(include_digest=False))).hexdigest()

    def to_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        payload: dict[str, Any] = {
            "attestation_id": self.attestation_id,
            "subject_id": self.subject_id,
            "verified": self.verified,
            "checks": list(self.checks),
            "failures": list(self.failures),
        }
        if include_digest:
            payload["digest"] = self.digest
        return payload
