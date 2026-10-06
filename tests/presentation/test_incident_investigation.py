"""Regression tests for read-only incident and recovery investigation projections."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import cast

import pytest

from statewake.adapters.incident_evidence import StoredIncidentRecord
from statewake.domain.security_incident import (
    AffectedTrustState,
    IncidentEvidenceReference,
    PostRecoveryVerification,
    RecoveryEvidence,
    SecurityIncidentEvidence,
    derive_incident_id,
)
from statewake.presentation.incident_investigation import (
    IncidentInvestigationQuery,
    build_incident_detail,
    build_incident_investigation,
    consolidate_incident_records,
)


def _incident(status: str, *, event_id: str = "event-1") -> SecurityIncidentEvidence:
    detected_at = datetime(2026, 9, 29, 7, tzinfo=UTC)
    incident_id = derive_incident_id(
        event_id=event_id,
        detected_at=detected_at,
        actor="detector",
        category="storage-compromise",
    )
    evidence = IncidentEvidenceReference("evidence", f"e-{event_id}", "a" * 64)
    refs: tuple[IncidentEvidenceReference, ...] = (evidence,)
    recovery = None
    post = None
    if status in {"recovered", "reverified"}:
        recovery_ref = IncidentEvidenceReference("recovery", f"r-{event_id}", "b" * 64)
        refs = (evidence, recovery_ref)
        recovery = RecoveryEvidence(
            f"r-{event_id}", recovery_ref, "operator", incident_id, "applied"
        )
    if status == "reverified":
        post = PostRecoveryVerification(
            f"v-{event_id}",
            (evidence,),
            "verifier",
            "verified",
            datetime(2026, 9, 29, 8, tzinfo=UTC),
        )
    return SecurityIncidentEvidence(
        incident_id=incident_id,
        event_id=event_id,
        detected_at=detected_at,
        actor="detector",
        category="storage-compromise",
        status=status,  # type: ignore[arg-type]
        evidence_refs=refs,
        affected_states=(AffectedTrustState("state-1", "c" * 64, "trust-v1"),),
        security_event_digests=("d" * 64,),
        uncertainty=("external source availability is not established",),
        recovery=recovery,
        post_recovery=post,
    )


def _stored(
    sequence: int, incident: SecurityIncidentEvidence, minute: int
) -> StoredIncidentRecord:
    recorded_at = datetime(2026, 9, 29, 7, minute, tzinfo=UTC)
    previous = None
    payload = {
        "sequence": sequence,
        "recorded_at": recorded_at.isoformat(),
        "incident": incident.to_dict(),
        "previous_digest": previous,
    }
    digest = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return StoredIncidentRecord(sequence, recorded_at, incident, previous, digest)


def test_incident_portfolio_keeps_recovery_and_reverification_distinct() -> None:
    preserved = _stored(0, _incident("preserved"), 1)
    recovered = _stored(1, _incident("recovered"), 2)
    reverified = _stored(2, _incident("reverified"), 3)
    projection = build_incident_investigation(
        (preserved, recovered, reverified), IncidentInvestigationQuery()
    ).to_dict()
    raw_items = projection["items"]
    raw_scope = projection["scope"]
    assert isinstance(raw_items, list)
    assert isinstance(raw_scope, dict)
    items = cast(list[dict[str, object]], raw_items)
    scope = cast(dict[str, object], raw_scope)
    item = items[0]
    assert item["status"] == "reverified"
    assert item["recovery"] == {"recorded": True, "status": "applied"}
    assert item["post_recovery"] == {"recorded": True, "status": "verified"}
    assert item["forensic_continuity_verified"] is True
    assert scope["store_records"] == 3


def test_incident_detail_hides_source_paths_and_preserves_reference_digests() -> None:
    incident = _incident("preserved")
    reference = replace(incident.evidence_refs[0], source="private/incident/input.json")
    incident = replace(incident, evidence_refs=(reference,))
    detail = build_incident_detail(
        (_stored(0, incident, 1),), incident.incident_id
    ).to_dict()
    assert detail["evidence_refs"] == [
        {
            "kind": "evidence",
            "identity": "e-event-1",
            "digest": "a" * 64,
            "source_recorded": True,
        }
    ]
    assert "private/incident/input.json" not in json.dumps(detail)
    assert detail["forensic_continuity"] == {
        "required": False,
        "verified": False,
        "causality_established": False,
    }


def test_incident_filters_are_exact_and_text_search_is_bounded() -> None:
    first = _stored(0, _incident("preserved", event_id="alpha"), 1)
    second = _stored(1, _incident("reverified", event_id="beta"), 2)
    projection = build_incident_investigation(
        (first, second),
        IncidentInvestigationQuery(status="reverified", text="BETA", limit=10),
    ).to_dict()
    raw_scope = projection["scope"]
    raw_items = projection["items"]
    assert isinstance(raw_scope, dict)
    assert isinstance(raw_items, list)
    scope = cast(dict[str, object], raw_scope)
    items = cast(list[dict[str, object]], raw_items)
    assert scope["matched_incidents"] == 1
    assert items[0]["event_id"] == "beta"
    with pytest.raises(ValueError, match="unsupported incident status"):
        IncidentInvestigationQuery(status="closed")
    with pytest.raises(ValueError, match="search limit"):
        IncidentInvestigationQuery(text="x" * 201)


def test_incident_lifecycle_rejects_status_or_timestamp_regression() -> None:
    recovered = _stored(0, _incident("recovered"), 2)
    preserved = _stored(1, _incident("preserved"), 3)
    with pytest.raises(ValueError, match="status regressed"):
        consolidate_incident_records((recovered, preserved))

    later = _stored(0, _incident("preserved"), 2)
    earlier = replace(
        _stored(1, _incident("recovered"), 3),
        recorded_at=later.recorded_at - timedelta(minutes=1),
    )
    with pytest.raises(ValueError, match="timestamps regressed"):
        consolidate_incident_records((later, earlier))


def test_incident_detail_rejects_unknown_identity() -> None:
    incident = _incident("preserved")
    with pytest.raises(FileNotFoundError):
        build_incident_detail((_stored(0, incident, 1),), "f" * 64)


def test_incident_domain_rejects_changed_immutable_detection_context() -> None:
    with pytest.raises(
        ValueError, match="incident_id is not the deterministic identity"
    ):
        replace(_incident("recovered"), actor="different-actor")
