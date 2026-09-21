"""Regression tests for Tier 14 security-incident evidence continuity."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from statewake.adapters.deployment_security import SecurityEvent
from statewake.adapters.incident_evidence import JsonlIncidentEvidenceStore
from statewake.adapters.security_audit import JsonlSecurityAuditStore
from statewake.domain.reliability_evidence import EvidenceReference
from statewake.domain.security_incident import (
    AffectedTrustState,
    IncidentEvidenceReference,
    IncidentStatus,
    KeyCompromiseImpact,
    PostRecoveryVerification,
    RecoveryEvidence,
    SecurityIncidentEvidence,
    bind_existing_evidence_reference,
    build_incident_timeline,
    derive_incident_id,
    reconstruct_security_state,
)


def _incident(
    status: str = "preserved", category: str = "storage-compromise"
) -> SecurityIncidentEvidence:
    """Build a deterministic incident fixture for the tests."""
    detected_at = datetime(2026, 9, 16, tzinfo=UTC)
    incident_id = derive_incident_id(
        event_id="event-1", detected_at=detected_at, actor="detector", category=category
    )
    evidence = IncidentEvidenceReference("evidence", "e1", "a" * 64)
    affected = AffectedTrustState("state-1", "b" * 64, "trust-v1")
    evidence_refs: tuple[IncidentEvidenceReference, ...] = (evidence,)
    key_compromise: KeyCompromiseImpact | None = None
    recovery: RecoveryEvidence | None = None
    post_recovery: PostRecoveryVerification | None = None
    if status in {"recovered", "reverified"}:
        recovery_ref = IncidentEvidenceReference("recovery", "r1", "c" * 64)
        recovery = RecoveryEvidence(
            "r1", recovery_ref, "operator", incident_id, "applied"
        )
        evidence_refs = (evidence, recovery_ref)
    if status == "reverified":
        post_recovery = PostRecoveryVerification(
            "v1",
            (evidence,),
            "verifier",
            "verified",
            datetime(2026, 9, 16, 1, tzinfo=UTC),
        )
    return SecurityIncidentEvidence(
        incident_id=incident_id,
        event_id="event-1",
        detected_at=detected_at,
        actor="detector",
        category=category,
        status=cast(IncidentStatus, status),
        evidence_refs=evidence_refs,
        affected_states=(affected,),
        security_event_digests=("d" * 64,),
        key_compromise=key_compromise,
        recovery=recovery,
        post_recovery=post_recovery,
    )


def test_incident_identity_is_deterministic_and_causal_claims_are_not_inferred() -> (
    None
):
    """Ensure identity is stable while timestamps remain observational context."""
    incident = _incident()
    payload = incident.to_dict()
    assert payload["incident_digest"] == incident.digest()
    reconstructed = reconstruct_security_state(incident, available_evidence_ids={"e1"})
    assert reconstructed["complete"] is False
    assert reconstructed["causality_established"] is False


def test_preservation_precedes_recovery() -> None:
    """Prevent an incident from claiming recovery without preserved evidence."""
    detected_at = datetime(2026, 9, 16, tzinfo=UTC)
    incident_id = derive_incident_id(
        event_id="e2",
        detected_at=detected_at,
        actor="actor",
        category="malicious-state-transition",
    )
    with pytest.raises(
        ValueError, match="recovered incident requires recovery evidence"
    ):
        SecurityIncidentEvidence(
            incident_id=incident_id,
            event_id="e2",
            detected_at=detected_at,
            actor="actor",
            category="malicious-state-transition",
            status="recovered",
            evidence_refs=(IncidentEvidenceReference("evidence", "e", "a" * 64),),
            affected_states=(),
            security_event_digests=(),
        )


def test_malicious_state_transition_records_affected_trust_state() -> None:
    """Record the trust state affected by a malicious transition explicitly."""
    incident = _incident(category="malicious-state-transition")
    state = incident.affected_states[0]
    assert state.state_id == "state-1"
    assert state.state_digest == "b" * 64
    assert state.trust_context == "trust-v1"


def test_key_compromise_records_blast_radius() -> None:
    """Record key version, attestation scope, evidence, and exposure window."""
    key = KeyCompromiseImpact(
        "key-1",
        "v9",
        ("att-1", "att-2"),
        (IncidentEvidenceReference("attestation", "att-1", "a" * 64),),
        datetime(2026, 9, 1, tzinfo=UTC),
        datetime(2026, 9, 2, tzinfo=UTC),
    )
    assert key.affected_key_version == "v9"
    assert key.affected_attestation_ids == ("att-1", "att-2")


def test_incident_reconstruction_marks_missing_evidence_explicitly() -> None:
    """Do not turn missing evidence into a false complete reconstruction."""
    incident = _incident()
    result = reconstruct_security_state(incident, available_evidence_ids=set())
    assert result["missing_evidence"] == ["e1"]
    assert result["complete"] is False


def test_incident_identity_is_deterministic() -> None:
    """Derive the incident identity from immutable event context rather than insertion order."""
    first = _incident()
    second = _incident()
    assert first.deterministic_identity() == second.deterministic_identity()
    assert first.incident_id == first.deterministic_identity()


def test_incident_during_ingestion_or_attestation_retains_both_evidence_links() -> None:
    """Keep ingestion and attestation observations in one preserved incident set."""
    evidence = (
        IncidentEvidenceReference("ingestion", "ingest-1", "a" * 64),
        IncidentEvidenceReference("attestation", "attest-1", "b" * 64),
    )
    detected_at = datetime(2026, 9, 16, tzinfo=UTC)
    incident_id = derive_incident_id(
        event_id="event-ingest-attest",
        detected_at=detected_at,
        actor="detector",
        category="ingestion-attestation-incident",
    )
    incident = SecurityIncidentEvidence(
        incident_id=incident_id,
        event_id="event-ingest-attest",
        detected_at=detected_at,
        actor="detector",
        category="ingestion-attestation-incident",
        status="preserved",
        evidence_refs=evidence,
        affected_states=(AffectedTrustState("state-1", "c" * 64, "trust-v1"),),
        security_event_digests=(),
    )
    assert {item.kind for item in incident.evidence_refs} == {
        "ingestion",
        "attestation",
    }


def test_recovery_and_post_recovery_links_preserve_incident_continuity() -> None:
    """Require recovery and verification to remain bound to the incident evidence set."""
    incident = _incident("reverified")
    incident.verify_forensic_continuity()
    assert incident.recovery is not None
    assert incident.recovery.source_incident_id == incident.incident_id
    assert incident.post_recovery is not None
    assert incident.post_recovery.status == "verified"


def test_recovery_evidence_outside_preserved_set_is_rejected() -> None:
    """Require destructive recovery evidence itself to be preserved before reconstruction."""
    base = _incident("reverified")
    assert base.recovery is not None
    external = IncidentEvidenceReference("recovery", "external-recovery", "e" * 64)
    invalid = SecurityIncidentEvidence(
        incident_id=base.incident_id,
        event_id=base.event_id,
        detected_at=base.detected_at,
        actor=base.actor,
        category=base.category,
        status=base.status,
        evidence_refs=base.evidence_refs,
        affected_states=base.affected_states,
        security_event_digests=base.security_event_digests,
        recovery=RecoveryEvidence(
            "external-recovery", external, "operator", base.incident_id, "applied"
        ),
        post_recovery=base.post_recovery,
    )
    with pytest.raises(ValueError, match="recovery evidence is outside"):
        invalid.verify_forensic_continuity()


def test_post_recovery_evidence_outside_preserved_set_is_rejected() -> None:
    """Reject reconstruction when post-recovery verification references unpreserved data."""
    base = _incident("reverified")
    assert base.recovery is not None
    assert base.post_recovery is not None
    external = IncidentEvidenceReference("external", "external-1", "e" * 64)
    invalid = SecurityIncidentEvidence(
        incident_id=base.incident_id,
        event_id=base.event_id,
        detected_at=base.detected_at,
        actor=base.actor,
        category=base.category,
        status=base.status,
        evidence_refs=base.evidence_refs,
        affected_states=base.affected_states,
        security_event_digests=base.security_event_digests,
        recovery=base.recovery,
        post_recovery=PostRecoveryVerification(
            "v2",
            (external,),
            "verifier",
            "verified",
            datetime(2026, 9, 16, 2, tzinfo=UTC),
        ),
    )
    with pytest.raises(ValueError, match="outside the preserved incident set"):
        invalid.verify_forensic_continuity()


def test_incident_store_is_hash_linked_and_tamper_evident(tmp_path: Path) -> None:
    """Persist incidents as a durable integrity chain and reject record mutation."""
    path = tmp_path / "incidents.jsonl"
    store = JsonlIncidentEvidenceStore(path)
    first = store.append(_incident())
    assert first.previous_digest is None
    second = store.append(_incident())
    assert second.previous_digest == first.digest
    assert len(store.read()) == 2

    payload = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    payload["incident"]["category"] = "tampered"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="incident_id|digest"):
        store.read()


def test_partial_incident_record_is_detected(tmp_path: Path) -> None:
    """Treat a truncated persisted incident record as invalid forensic evidence."""
    path = tmp_path / "incidents.jsonl"
    store = JsonlIncidentEvidenceStore(path)
    store.append(_incident())
    raw = path.read_bytes()
    path.write_bytes(raw[:-10])
    with pytest.raises(ValueError, match="invalid incident evidence record"):
        store.read()


def test_security_audit_digest_can_be_reused_without_replicating_the_audit_stream(
    tmp_path: Path,
) -> None:
    """Bind existing security-audit records into incident evidence by digest only."""
    audit_store = JsonlSecurityAuditStore(tmp_path / "audit.jsonl")
    audit = audit_store.append(
        SecurityEvent(
            event="request_rejected",
            operation="verify:evidence",
            method="POST",
            path="/v1/evidence/verify",
            reason="security_incident",
        )
    )
    evidence = bind_existing_evidence_reference(
        EvidenceReference("security-audit", "audit-1", audit.digest)
    )
    incident = _incident()
    assert evidence.digest == audit.digest
    assert incident.security_event_digests == ("d" * 64,)


def test_timeline_makes_observation_order_explicit_without_claiming_causality() -> None:
    """Represent detect/preserve/contain ordering independently of causal inference."""
    incident = _incident()
    timeline = build_incident_timeline(
        incident,
        preserved_at=datetime(2026, 9, 16, 1, tzinfo=UTC),
        contained_at=datetime(2026, 9, 16, 2, tzinfo=UTC),
    )
    assert [status for status, _ in timeline.entries] == [
        "detected",
        "preserved",
        "contained",
    ]
