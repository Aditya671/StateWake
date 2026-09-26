"""Portable, human-readable reliability verification report contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Any


@dataclass(frozen=True, slots=True)
class ReliabilityVerificationReport:
    """Score-free inspection artifact for a bounded reliability claim.

    The report is intentionally broader than the older release-proof rendering:
    it can carry candidate identity, missing evidence, unrun/unknown checks,
    residual risk, and human-decision boundaries without becoming an approval.
    """

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
    candidate_identity: str = "not-specified"
    candidate_digest: str = "not-specified"
    report_type: str = "engineering"
    evidence_missing: tuple[str, ...] = ()
    checks_unrun: tuple[str, ...] = ()
    checks_unknown: tuple[str, ...] = ()
    residual_risks: tuple[str, ...] = ()
    human_decisions_required: tuple[str, ...] = ()
    allowed_use: tuple[str, ...] = ()
    prohibited_use: tuple[str, ...] = ()
    machine_readable_appendix: tuple[str, ...] = ()
    artifact_digests: tuple[str, ...] = ()
    profile_evaluation_digest: str | None = None
    approval_status: str = "not-approval"

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
        if not self.candidate_identity.strip() or not self.candidate_digest.strip():
            raise ValueError("candidate identity and digest must not be empty.")
        if self.verified and self.checks_failed:
            raise ValueError("verified report cannot contain failed checks.")
        if self.verified and self.evidence_missing:
            raise ValueError("verified report cannot contain missing evidence.")
        if self.verified and self.checks_unknown:
            raise ValueError("verified report cannot contain unknown checks.")
        if self.verified and self.checks_unrun:
            raise ValueError("verified report cannot contain unrun checks.")
        if not self.verified and not (
            self.checks_failed
            or self.evidence_missing
            or self.checks_unrun
            or self.checks_unknown
            or self.evidence_omitted
        ):
            raise ValueError(
                "unverified report must contain failed, missing, unrun, unknown, "
                "or omitted evidence."
            )
        passed = set(self.checks_passed)
        blocked = (
            set(self.checks_failed) | set(self.checks_unrun) | set(self.checks_unknown)
        )
        overlap = passed & blocked
        if overlap:
            raise ValueError("a check cannot be both passed and blocked.")
        if self.approval_status not in {
            "not-approval",
            "requires-human-approval",
            "approved",
        }:
            raise ValueError("unsupported approval_status.")
        if self.approval_status == "approved" and not self.human_decisions_required:
            raise ValueError("approved reports must identify the human decision scope.")

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            "format_version": self.format_version,
            "candidate_identity": self.candidate_identity,
            "candidate_digest": self.candidate_digest,
            "report_type": self.report_type,
            "claim": self.claim,
            "decision": self.decision,
            "approval_status": self.approval_status,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "profile_evaluation_digest": self.profile_evaluation_digest,
            "verified": self.verified,
            "evidence_included": list(self.evidence_included),
            "evidence_omitted": list(self.evidence_omitted),
            "evidence_missing": list(self.evidence_missing),
            "checks_passed": list(self.checks_passed),
            "checks_failed": list(self.checks_failed),
            "checks_unrun": list(self.checks_unrun),
            "checks_unknown": list(self.checks_unknown),
            "source_identities": list(self.source_identities),
            "artifact_digests": list(self.artifact_digests),
            "rationale": list(self.rationale),
            "caveats": list(self.caveats),
            "residual_risks": list(self.residual_risks),
            "allowed_use": list(self.allowed_use),
            "prohibited_use": list(self.prohibited_use),
            "human_decisions_required": list(self.human_decisions_required),
            "recovery_status": self.recovery_status,
            "machine_readable_appendix": list(self.machine_readable_appendix),
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
