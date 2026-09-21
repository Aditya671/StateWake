"""Portable Tier 14 structural verifier for forensic continuity."""

from __future__ import annotations

from datetime import UTC, datetime

from statewake.domain.security_incident import (
    AffectedTrustState,
    IncidentEvidenceReference,
    KeyCompromiseImpact,
    PostRecoveryVerification,
    RecoveryEvidence,
    SecurityIncidentEvidence,
    derive_incident_id,
)


def verify_forensic_continuity() -> None:
    """Exercise the minimum Tier 14 construction and continuity invariants."""
    evidence = IncidentEvidenceReference(
        "verification",
        "verify-1",
        "a" * 64,
    )
    recovery_evidence = IncidentEvidenceReference("recovery", "recovery-1", "b" * 64)
    verification_evidence = IncidentEvidenceReference(
        "post-recovery", "verify-1", "a" * 64
    )
    state = AffectedTrustState("state-1", "c" * 64, "trust-root-v1")
    key = KeyCompromiseImpact(
        key_identity="key-1",
        affected_key_version="v7",
        affected_attestation_ids=("attestation-1",),
        affected_evidence=(evidence,),
        exposure_start=datetime(2026, 9, 16, tzinfo=UTC),
    )
    detected_at = datetime(2026, 9, 16, tzinfo=UTC)
    incident_id = derive_incident_id(
        event_id="event-1",
        detected_at=detected_at,
        actor="detector",
        category="trust-checkpoint-discrepancy",
    )
    recovery = RecoveryEvidence(
        "recovery-1",
        recovery_evidence,
        "operator",
        incident_id,
        "applied",
    )
    verification = PostRecoveryVerification(
        "verification-1",
        (verification_evidence,),
        "verifier",
        "verified",
        datetime(2026, 9, 16, 1, tzinfo=UTC),
    )
    incident = SecurityIncidentEvidence(
        incident_id=incident_id,
        event_id="event-1",
        detected_at=detected_at,
        actor="detector",
        category="trust-checkpoint-discrepancy",
        status="reverified",
        evidence_refs=(evidence, recovery_evidence),
        affected_states=(state,),
        security_event_digests=("d" * 64,),
        key_compromise=key,
        recovery=recovery,
        post_recovery=verification,
    )
    incident.verify_forensic_continuity()
    if incident.digest() != incident.incident_digest and incident.incident_digest:
        raise ValueError("Tier 14 incident digest must be deterministic")
    if incident.digest() != incident.to_dict()["incident_digest"]:
        raise ValueError("Tier 14 incident digest serialization mismatch")


if __name__ == "__main__":
    verify_forensic_continuity()
    print("TIER14_FORENSIC_CONTINUITY: PASS")
