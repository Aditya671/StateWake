"""Portable, human-readable reliability verification report contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any


@dataclass(frozen=True, slots=True)
class ReliabilityVerificationReport:
    """Score-free inspection artifact for a bounded reliability claim."""

    format_version: str
    claim: str
    decision: str
    profile_id: str
    profile_version: str
    verified: bool
    evidence_included: tuple[str, ...]
    evidence_omitted: tuple[str, ...]
    checks_passed: tuple[str, ...]
    checks_failed: tuple[str, ...]
    source_identities: tuple[str, ...]
    rationale: tuple[str, ...]
    caveats: tuple[str, ...]
    recovery_status: str
    verifier_version: str
    generated_at: str

    def __post_init__(self) -> None:
        """Validate and normalize the instance after initialization."""
        if self.format_version != "1":
            raise ValueError(
                "unsupported reliability verification report format version."
            )
        if (
            not self.claim.strip()
            or not self.profile_id.strip()
            or not self.profile_version.strip()
        ):
            raise ValueError("claim and profile identity must not be empty.")
        if self.verified and self.checks_failed:
            raise ValueError("verified report cannot contain failed checks.")
        if not self.verified and not self.checks_failed:
            raise ValueError("unverified report must contain failed checks.")

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            "format_version": self.format_version,
            "claim": self.claim,
            "decision": self.decision,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "verified": self.verified,
            "evidence_included": list(self.evidence_included),
            "evidence_omitted": list(self.evidence_omitted),
            "checks_passed": list(self.checks_passed),
            "checks_failed": list(self.checks_failed),
            "source_identities": list(self.source_identities),
            "rationale": list(self.rationale),
            "caveats": list(self.caveats),
            "recovery_status": self.recovery_status,
            "verifier_version": self.verifier_version,
            "generated_at": self.generated_at,
        }

    @property
    def digest(self) -> str:
        """Deterministic SHA-256 digest represented by this object."""
        return sha256(
            json.dumps(
                self.payload(),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to a dictionary."""
        return {**self.payload(), "digest": self.digest}
