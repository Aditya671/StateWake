"""Bounded read projections for canonical security-incident investigation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from statewake.adapters.incident_evidence import StoredIncidentRecord
from statewake.domain.security_incident import (
    IncidentEvidenceReference,
    IncidentStatus,
    SecurityIncidentEvidence,
)

INCIDENT_INVESTIGATION_SCHEMA_VERSION = "incident-investigation.v1"
INCIDENT_DETAIL_SCHEMA_VERSION = "incident-detail.v1"
MAX_INCIDENT_PAGE_LIMIT = 200
MAX_INCIDENT_FILTER_CHARS = 256
MAX_INCIDENT_TEXT_CHARS = 200
INCIDENT_STATUSES: tuple[IncidentStatus, ...] = (
    "detected",
    "preserved",
    "contained",
    "assessed",
    "recovered",
    "reverified",
)
_STATUS_RANK = {status: index for index, status in enumerate(INCIDENT_STATUSES)}


def _iso(value: datetime) -> str:
    """Return one stable timezone-aware timestamp."""
    if value.tzinfo is None:
        raise ValueError("incident timestamps must be timezone-aware")
    return value.isoformat()


def _evidence_ref(reference: IncidentEvidenceReference) -> dict[str, object]:
    """Render one evidence reference without exposing host filesystem paths."""
    kind = reference.kind
    identity = reference.identity
    digest = reference.digest
    source = reference.source
    return {
        "kind": str(kind),
        "identity": str(identity),
        "digest": str(digest),
        "source_recorded": source is not None,
    }


@dataclass(frozen=True, slots=True)
class IncidentInvestigationRecord:
    """All canonical store observations for one deterministic incident identity."""

    records: tuple[StoredIncidentRecord, ...]

    def __post_init__(self) -> None:
        """Require stable immutable context and monotonic lifecycle observations."""
        if not self.records:
            raise ValueError("incident investigation requires at least one record")
        first = self.records[0].incident
        previous_rank = -1
        previous_time: datetime | None = None
        for record in self.records:
            incident = record.incident
            if (
                incident.incident_id != first.incident_id
                or incident.event_id != first.event_id
                or incident.detected_at != first.detected_at
                or incident.actor != first.actor
                or incident.category != first.category
            ):
                raise ValueError(
                    "incident immutable context changed across observations"
                )
            rank = _STATUS_RANK[incident.status]
            if rank < previous_rank:
                raise ValueError("incident lifecycle status regressed")
            if previous_time is not None and record.recorded_at < previous_time:
                raise ValueError("incident observation timestamps regressed")
            previous_rank = rank
            previous_time = record.recorded_at

    @property
    def incident_id(self) -> str:
        """Return the deterministic incident identity."""
        return self.records[0].incident.incident_id

    @property
    def current(self) -> SecurityIncidentEvidence:
        """Return the latest verified incident observation in store order."""
        return self.records[-1].incident

    @property
    def latest_recorded_at(self) -> datetime:
        """Return the latest store observation timestamp."""
        return self.records[-1].recorded_at

    def summary_dict(self) -> dict[str, object]:
        """Return a bounded incident portfolio row."""
        incident = self.current
        return {
            "incident_id": incident.incident_id,
            "event_id": incident.event_id,
            "detected_at": _iso(incident.detected_at),
            "latest_recorded_at": _iso(self.latest_recorded_at),
            "actor": incident.actor,
            "category": incident.category,
            "status": incident.status,
            "observation_count": len(self.records),
            "evidence_ref_count": len(incident.evidence_refs),
            "affected_state_count": len(incident.affected_states),
            "uncertainty_count": len(incident.uncertainty),
            "key_compromise_recorded": incident.key_compromise is not None,
            "recovery": {
                "recorded": incident.recovery is not None,
                "status": None
                if incident.recovery is None
                else incident.recovery.status,
            },
            "post_recovery": {
                "recorded": incident.post_recovery is not None,
                "status": None
                if incident.post_recovery is None
                else incident.post_recovery.status,
            },
            "forensic_continuity_verified": _forensic_continuity(incident),
        }


@dataclass(frozen=True, slots=True)
class IncidentInvestigationQuery:
    """Allowlisted filters for the incident portfolio."""

    status: str | None = None
    category: str | None = None
    text: str | None = None
    limit: int = 50
    offset: int = 0

    def __post_init__(self) -> None:
        """Validate bounded filter and pagination values."""
        if self.status is not None and self.status not in INCIDENT_STATUSES:
            raise ValueError("unsupported incident status")
        if self.category is not None:
            if (
                not self.category.strip()
                or len(self.category) > MAX_INCIDENT_FILTER_CHARS
            ):
                raise ValueError("category is blank or exceeds the filter limit")
        if self.text is not None:
            if not self.text.strip() or len(self.text) > MAX_INCIDENT_TEXT_CHARS:
                raise ValueError("text is blank or exceeds the search limit")
        if self.limit < 1 or self.limit > MAX_INCIDENT_PAGE_LIMIT:
            raise ValueError(f"limit must be between 1 and {MAX_INCIDENT_PAGE_LIMIT}")
        if self.offset < 0:
            raise ValueError("offset must be non-negative")

    def matches(self, record: IncidentInvestigationRecord) -> bool:
        """Return whether one incident matches every configured filter."""
        incident = record.current
        if self.status is not None and incident.status != self.status:
            return False
        if self.category is not None and incident.category != self.category:
            return False
        if self.text is not None:
            needle = self.text.casefold()
            haystacks = (
                incident.incident_id,
                incident.event_id,
                incident.actor,
                incident.category,
                incident.status,
            )
            if not any(needle in value.casefold() for value in haystacks):
                return False
        return True

    def to_dict(self) -> dict[str, object]:
        """Return the normalized query contract."""
        return {
            "status": self.status,
            "category": self.category,
            "text": self.text,
            "limit": self.limit,
            "offset": self.offset,
        }


@dataclass(frozen=True, slots=True)
class IncidentInvestigationProjection:
    """One deterministic page of canonical incident investigations."""

    incidents: tuple[IncidentInvestigationRecord, ...]
    query: IncidentInvestigationQuery
    store_record_count: int

    def to_dict(self) -> dict[str, object]:
        """Return the stable portfolio representation."""
        matched = tuple(item for item in self.incidents if self.query.matches(item))
        start = self.query.offset
        page = matched[start : start + self.query.limit]
        next_offset = start + len(page)
        has_more = next_offset < len(matched)
        return {
            "schema_version": INCIDENT_INVESTIGATION_SCHEMA_VERSION,
            "scope": {
                "resource": "security-incident-evidence",
                "sort": "latest_recorded_at_desc_incident_id_asc",
                "store_records": self.store_record_count,
                "total_incidents": len(self.incidents),
                "matched_incidents": len(matched),
            },
            "query": self.query.to_dict(),
            "page": {
                "limit": self.query.limit,
                "offset": self.query.offset,
                "returned": len(page),
                "has_more": has_more,
                "next_offset": next_offset if has_more else None,
            },
            "items": [item.summary_dict() for item in page],
            "limitations": [
                "This view reconstructs recorded StateWake incident evidence; it is not an incident-response ticketing or remediation system.",
                "Recorded timestamps establish observation context and lifecycle order; they do not establish causality.",
                "Evidence references identify preserved dependencies but this portfolio view does not claim referenced payload bytes were independently reverified.",
                "A recovered incident remains distinct from a reverified incident with verified post-recovery evidence.",
            ],
        }

    @property
    def digest(self) -> str:
        """Return the deterministic conditional-read digest."""
        raw = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class IncidentDetailProjection:
    """Detailed read-only reconstruction of one incident's canonical observations."""

    investigation: IncidentInvestigationRecord

    def to_dict(self) -> dict[str, object]:
        """Return the stable incident detail representation."""
        incident = self.investigation.current
        key = incident.key_compromise
        recovery = incident.recovery
        post = incident.post_recovery
        return {
            "schema_version": INCIDENT_DETAIL_SCHEMA_VERSION,
            "incident": self.investigation.summary_dict(),
            "lifecycle": [
                {
                    "sequence": record.sequence,
                    "recorded_at": _iso(record.recorded_at),
                    "status": record.incident.status,
                    "record_digest": record.digest,
                    "incident_digest": record.incident.digest(),
                }
                for record in self.investigation.records
            ],
            "evidence_refs": [_evidence_ref(item) for item in incident.evidence_refs],
            "affected_states": [
                {
                    "state_id": item.state_id,
                    "state_digest": item.state_digest,
                    "trust_context": item.trust_context,
                    "affected_window_start": None
                    if item.affected_window_start is None
                    else _iso(item.affected_window_start),
                    "affected_window_end": None
                    if item.affected_window_end is None
                    else _iso(item.affected_window_end),
                }
                for item in incident.affected_states
            ],
            "security_event_digests": list(incident.security_event_digests),
            "uncertainty": list(incident.uncertainty),
            "key_compromise": None
            if key is None
            else {
                "key_identity": key.key_identity,
                "affected_key_version": key.affected_key_version,
                "affected_attestation_ids": list(key.affected_attestation_ids),
                "affected_evidence": [
                    _evidence_ref(item) for item in key.affected_evidence
                ],
                "exposure_start": _iso(key.exposure_start),
                "exposure_end": None
                if key.exposure_end is None
                else _iso(key.exposure_end),
            },
            "recovery": None
            if recovery is None
            else {
                "recovery_id": recovery.recovery_id,
                "actor": recovery.actor,
                "source_incident_id": recovery.source_incident_id,
                "status": recovery.status,
                "evidence_ref": _evidence_ref(recovery.evidence_ref),
            },
            "post_recovery": None
            if post is None
            else {
                "verification_id": post.verification_id,
                "actor": post.actor,
                "status": post.status,
                "performed_at": _iso(post.performed_at),
                "evidence_refs": [_evidence_ref(item) for item in post.evidence_refs],
            },
            "forensic_continuity": {
                "required": incident.status == "reverified",
                "verified": _forensic_continuity(incident),
                "causality_established": False,
            },
            "limitations": [
                "Recovery restores the strongest state justified by preserved evidence; it does not manufacture missing trust.",
                "Forensic-continuity verification checks the recorded reference relationships, not the truth or availability of external systems.",
                "Source filesystem paths are intentionally not exposed by this read projection.",
            ],
        }

    @property
    def digest(self) -> str:
        """Return the deterministic detail digest."""
        raw = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


def _forensic_continuity(incident: SecurityIncidentEvidence) -> bool:
    """Verify the stricter forensic relationship contract when applicable."""
    if incident.status != "reverified":
        return False
    incident.verify_forensic_continuity()
    return True


def consolidate_incident_records(
    records: tuple[StoredIncidentRecord, ...],
) -> tuple[IncidentInvestigationRecord, ...]:
    """Group verified store observations by deterministic incident identity."""
    grouped: dict[str, list[StoredIncidentRecord]] = {}
    for record in records:
        grouped.setdefault(record.incident.incident_id, []).append(record)
    investigations = tuple(
        IncidentInvestigationRecord(tuple(group)) for group in grouped.values()
    )
    by_identity = sorted(investigations, key=lambda item: item.incident_id)
    return tuple(
        sorted(
            by_identity,
            key=lambda item: item.latest_recorded_at,
            reverse=True,
        )
    )


def build_incident_investigation(
    records: tuple[StoredIncidentRecord, ...], query: IncidentInvestigationQuery
) -> IncidentInvestigationProjection:
    """Build one bounded portfolio page from a verified incident-evidence chain."""
    incidents = consolidate_incident_records(records)
    return IncidentInvestigationProjection(incidents, query, len(records))


def build_incident_detail(
    records: tuple[StoredIncidentRecord, ...], incident_id: str
) -> IncidentDetailProjection:
    """Build the detail projection for exactly one incident identity."""
    if len(incident_id) != 64 or any(
        char not in "0123456789abcdef" for char in incident_id
    ):
        raise ValueError("incident_id must be lowercase SHA-256 hex")
    for item in consolidate_incident_records(records):
        if item.incident_id == incident_id:
            return IncidentDetailProjection(item)
    raise FileNotFoundError(incident_id)


__all__ = [
    "INCIDENT_DETAIL_SCHEMA_VERSION",
    "INCIDENT_INVESTIGATION_SCHEMA_VERSION",
    "INCIDENT_STATUSES",
    "MAX_INCIDENT_FILTER_CHARS",
    "MAX_INCIDENT_PAGE_LIMIT",
    "MAX_INCIDENT_TEXT_CHARS",
    "IncidentDetailProjection",
    "IncidentInvestigationProjection",
    "IncidentInvestigationQuery",
    "IncidentInvestigationRecord",
    "build_incident_detail",
    "build_incident_investigation",
    "consolidate_incident_records",
]
