"""Bounded security-incident evidence and forensic continuity primitives."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Literal

from .reliability_evidence import EvidenceReference

IncidentStatus = Literal[
    "detected",
    "preserved",
    "contained",
    "assessed",
    "recovered",
    "reverified",
]

_HEX64 = frozenset("0123456789abcdef")
_STATUS_ORDER: dict[IncidentStatus, int] = {
    "detected": 0,
    "preserved": 1,
    "contained": 2,
    "assessed": 3,
    "recovered": 4,
    "reverified": 5,
}


def _digest(value: str, name: str) -> None:
    """Validate one lowercase SHA-256 digest string."""
    if len(value) != 64 or any(char not in _HEX64 for char in value):
        raise ValueError(f"{name} must be lowercase SHA-256 hex.")


def _canonical(payload: dict[str, Any]) -> bytes:
    """Return the deterministic representation used for incident identity."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _validate_time(value: datetime, name: str) -> None:
    """Validate a timezone-aware timestamp."""
    if value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware.")


def derive_incident_id(
    *, event_id: str, detected_at: datetime, actor: str, category: str
) -> str:
    """Derive a deterministic incident identity from immutable detection context."""
    for name, value in (
        ("event_id", event_id),
        ("actor", actor),
        ("category", category),
    ):
        if not value.strip():
            raise ValueError(f"{name} must not be empty.")
    _validate_time(detected_at, "detected_at")
    payload = {
        "event_id": event_id,
        "detected_at": detected_at.astimezone(UTC).isoformat(),
        "actor": actor,
        "category": category,
    }
    return sha256(_canonical(payload)).hexdigest()


def _validate_status(value: IncidentStatus) -> IncidentStatus:
    """Validate one incident lifecycle status."""
    if value not in _STATUS_ORDER:
        raise ValueError(f"unsupported incident status: {value}")
    return value


@dataclass(frozen=True, slots=True)
class IncidentEvidenceReference:
    """Reference to evidence preserved for later reconstruction."""

    kind: str
    identity: str
    digest: str
    source: str | None = None

    def __post_init__(self) -> None:
        """Validate the reference without copying evidence payloads."""
        if not self.kind.strip() or not self.identity.strip():
            raise ValueError("evidence kind and identity must not be empty.")
        _digest(self.digest, "digest")
        if self.source is not None and not self.source.strip():
            raise ValueError("source must not be blank when provided.")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical evidence-reference representation."""
        return {
            "kind": self.kind,
            "identity": self.identity,
            "digest": self.digest,
            "source": self.source,
        }


@dataclass(frozen=True, slots=True)
class AffectedTrustState:
    """Describe one StateWake state or trust context affected by an incident."""

    state_id: str
    state_digest: str
    trust_context: str
    affected_window_start: datetime | None = None
    affected_window_end: datetime | None = None

    def __post_init__(self) -> None:
        """Validate the affected-state record."""
        for name in ("state_id", "trust_context"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        _digest(self.state_digest, "state_digest")
        if (self.affected_window_start is None) != (self.affected_window_end is None):
            raise ValueError("affected time window must have both endpoints.")
        if self.affected_window_start is not None:
            _validate_time(self.affected_window_start, "affected_window_start")

        if self.affected_window_end is not None:
            _validate_time(self.affected_window_end, "affected_window_end")

        # Only compare if both are present
        if (
            self.affected_window_start is not None
            and self.affected_window_end is not None
        ):
            if self.affected_window_end < self.affected_window_start:
                raise ValueError("affected time window end precedes its start.")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical affected-state representation."""
        return {
            "state_id": self.state_id,
            "state_digest": self.state_digest,
            "trust_context": self.trust_context,
            "affected_window_start": None
            if self.affected_window_start is None
            else self.affected_window_start.astimezone(UTC).isoformat(),
            "affected_window_end": None
            if self.affected_window_end is None
            else self.affected_window_end.astimezone(UTC).isoformat(),
        }


@dataclass(frozen=True, slots=True)
class KeyCompromiseImpact:
    """Bound a signing-key compromise to explicit versions, evidence, and time."""

    key_identity: str
    affected_key_version: str
    affected_attestation_ids: tuple[str, ...]
    affected_evidence: tuple[IncidentEvidenceReference, ...]
    exposure_start: datetime
    exposure_end: datetime | None = None

    def __post_init__(self) -> None:
        """Validate key-compromise blast-radius metadata."""
        for name in ("key_identity", "affected_key_version"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        if any(not value.strip() for value in self.affected_attestation_ids):
            raise ValueError("affected attestation IDs must not be blank.")
        _validate_time(self.exposure_start, "exposure_start")
        if self.exposure_end is not None:
            _validate_time(self.exposure_end, "exposure_end")
            if self.exposure_end < self.exposure_start:
                raise ValueError("exposure_end precedes exposure_start.")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical blast-radius representation."""
        return {
            "key_identity": self.key_identity,
            "affected_key_version": self.affected_key_version,
            "affected_attestation_ids": list(self.affected_attestation_ids),
            "affected_evidence": [item.to_dict() for item in self.affected_evidence],
            "exposure_start": self.exposure_start.astimezone(UTC).isoformat(),
            "exposure_end": None
            if self.exposure_end is None
            else self.exposure_end.astimezone(UTC).isoformat(),
        }


@dataclass(frozen=True, slots=True)
class RecoveryEvidence:
    """Bind a recovery action to the evidence and incident it addresses."""

    recovery_id: str
    evidence_ref: IncidentEvidenceReference
    actor: str
    source_incident_id: str
    status: Literal["planned", "applied", "failed"]

    def __post_init__(self) -> None:
        """Validate recovery attribution and incident binding."""
        for name in ("recovery_id", "actor", "source_incident_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        if self.status not in {"planned", "applied", "failed"}:
            raise ValueError("unsupported recovery evidence status")
        if self.status == "applied" and not self.source_incident_id.strip():
            raise ValueError("applied recovery must reference its source incident")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical recovery-evidence representation."""
        return {
            "recovery_id": self.recovery_id,
            "evidence_ref": self.evidence_ref.to_dict(),
            "actor": self.actor,
            "source_incident_id": self.source_incident_id,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class PostRecoveryVerification:
    """Record the evidence-backed verification performed after recovery."""

    verification_id: str
    evidence_refs: tuple[IncidentEvidenceReference, ...]
    actor: str
    status: Literal["verified", "failed", "unknown"]
    performed_at: datetime

    def __post_init__(self) -> None:
        """Validate post-recovery verification evidence."""
        if not self.verification_id.strip() or not self.actor.strip():
            raise ValueError("verification_id and actor must not be empty.")
        if self.status not in {"verified", "failed", "unknown"}:
            raise ValueError("unsupported post-recovery verification status")
        if not self.evidence_refs:
            raise ValueError("post-recovery verification requires evidence refs")
        _validate_time(self.performed_at, "performed_at")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical post-recovery verification representation."""
        return {
            "verification_id": self.verification_id,
            "evidence_refs": [item.to_dict() for item in self.evidence_refs],
            "actor": self.actor,
            "status": self.status,
            "performed_at": self.performed_at.astimezone(UTC).isoformat(),
        }


@dataclass(frozen=True, slots=True)
class SecurityIncidentEvidence:
    """Immutable forensic-continuity record for one StateWake security incident."""

    incident_id: str
    event_id: str
    detected_at: datetime
    actor: str
    category: str
    status: IncidentStatus
    evidence_refs: tuple[IncidentEvidenceReference, ...]
    affected_states: tuple[AffectedTrustState, ...]
    security_event_digests: tuple[str, ...]
    uncertainty: tuple[str, ...] = ()
    key_compromise: KeyCompromiseImpact | None = None
    recovery: RecoveryEvidence | None = None
    post_recovery: PostRecoveryVerification | None = None
    incident_digest: str = ""

    def __post_init__(self) -> None:
        """Validate incident lifecycle ordering and deterministic identity."""
        for name in ("incident_id", "event_id", "actor", "category"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        _validate_time(self.detected_at, "detected_at")
        status = _validate_status(self.status)
        if not self.evidence_refs:
            raise ValueError(
                "incident evidence must preserve at least one evidence ref"
            )
        if any(not value.strip() for value in self.uncertainty):
            raise ValueError("uncertainty entries must not be blank")
        expected_identity = derive_incident_id(
            event_id=self.event_id,
            detected_at=self.detected_at,
            actor=self.actor,
            category=self.category,
        )
        if self.incident_id != expected_identity:
            raise ValueError(
                "incident_id is not the deterministic identity of its event context"
            )
        for digest in self.security_event_digests:
            _digest(digest, "security_event_digest")
        if status in {"preserved", "contained", "assessed", "recovered", "reverified"}:
            if not self.evidence_refs:
                raise ValueError("preservation state requires preserved evidence")
        if status in {"recovered", "reverified"} and self.recovery is None:
            raise ValueError("recovered incident requires recovery evidence")
        if status == "reverified":
            if self.post_recovery is None:
                raise ValueError(
                    "reverified incident requires post-recovery verification"
                )
            if self.post_recovery.status != "verified":
                raise ValueError(
                    "reverified incident requires verified post-recovery evidence"
                )
        if (
            self.recovery is not None
            and self.recovery.source_incident_id != self.incident_id
        ):
            raise ValueError("recovery evidence must bind to this incident")
        if self.incident_digest and self.incident_digest != self.digest():
            raise ValueError("security incident evidence digest mismatch")

    def payload(self) -> dict[str, Any]:
        """Return the canonical incident payload excluding its own digest."""
        return {
            "incident_id": self.incident_id,
            "event_id": self.event_id,
            "detected_at": self.detected_at.astimezone(UTC).isoformat(),
            "actor": self.actor,
            "category": self.category,
            "status": self.status,
            "evidence_refs": [item.to_dict() for item in self.evidence_refs],
            "affected_states": [item.to_dict() for item in self.affected_states],
            "security_event_digests": list(self.security_event_digests),
            "uncertainty": list(self.uncertainty),
            "key_compromise": None
            if self.key_compromise is None
            else self.key_compromise.to_dict(),
            "recovery": None if self.recovery is None else self.recovery.to_dict(),
            "post_recovery": None
            if self.post_recovery is None
            else self.post_recovery.to_dict(),
        }

    def deterministic_identity(self) -> str:
        """Return a deterministic identity derived from immutable event context."""
        identity_payload = {
            "event_id": self.event_id,
            "detected_at": self.detected_at.astimezone(UTC).isoformat(),
            "actor": self.actor,
            "category": self.category,
        }
        return sha256(_canonical(identity_payload)).hexdigest()

    def digest(self) -> str:
        """Return the deterministic SHA-256 digest of the complete incident record."""
        return sha256(_canonical(self.payload())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical incident record including its digest."""
        return {
            "format_version": "1",
            **self.payload(),
            "incident_digest": self.digest(),
        }

    def verify_forensic_continuity(self) -> None:
        """Validate the evidence links required to reconstruct security-relevant state."""
        if self.status != "reverified":
            raise ValueError("forensic reconstruction requires a reverified incident")
        if self.post_recovery is None or self.post_recovery.status != "verified":
            raise ValueError("post-recovery verification is missing or not verified")
        if self.recovery is None or self.recovery.status != "applied":
            raise ValueError("applied recovery evidence is missing")
        referenced = {reference.identity for reference in self.evidence_refs}
        if self.recovery.evidence_ref.identity not in referenced:
            raise ValueError("recovery evidence is outside the preserved incident set")
        for verification_ref in self.post_recovery.evidence_refs:
            if verification_ref.identity not in referenced:
                raise ValueError(
                    "post-recovery verification references evidence outside the preserved incident set"
                )


@dataclass(frozen=True, slots=True)
class IncidentTimeline:
    """Structured lifecycle view that prevents status from implying causality."""

    incident_id: str
    entries: tuple[tuple[IncidentStatus, datetime], ...]

    def __post_init__(self) -> None:
        """Validate monotonic incident lifecycle timestamps."""
        if not self.incident_id.strip():
            raise ValueError("incident_id must not be empty")
        previous_rank = -1
        previous_time: datetime | None = None
        for status, occurred_at in self.entries:
            rank = _STATUS_ORDER[status]
            _validate_time(occurred_at, "timeline timestamp")
            if rank <= previous_rank:
                raise ValueError("incident timeline statuses must advance strictly")
            if previous_time is not None and occurred_at < previous_time:
                raise ValueError("incident timeline timestamps must be monotonic")
            previous_rank = rank
            previous_time = occurred_at


def build_incident_timeline(
    incident: SecurityIncidentEvidence,
    *,
    preserved_at: datetime,
    contained_at: datetime | None = None,
    assessed_at: datetime | None = None,
    recovered_at: datetime | None = None,
    reverified_at: datetime | None = None,
) -> IncidentTimeline:
    """Build an ordered lifecycle timeline from immutable incident evidence."""
    values: list[tuple[IncidentStatus, datetime]] = [
        ("detected", incident.detected_at),
        ("preserved", preserved_at),
    ]
    optional: tuple[tuple[IncidentStatus, datetime | None], ...] = (
        ("contained", contained_at),
        ("assessed", assessed_at),
        ("recovered", recovered_at),
        ("reverified", reverified_at),
    )
    values.extend((status, timestamp) for status, timestamp in optional if timestamp)
    return IncidentTimeline(incident.incident_id, tuple(values))


def reconstruct_security_state(
    incident: SecurityIncidentEvidence,
    *,
    available_evidence_ids: set[str],
) -> dict[str, Any]:
    """Return bounded reconstruction facts and explicitly mark missing dependencies."""
    missing = sorted(
        reference.identity
        for reference in incident.evidence_refs
        if reference.identity not in available_evidence_ids
    )
    return {
        "incident_id": incident.incident_id,
        "security_event_digests": list(incident.security_event_digests),
        "affected_state_ids": [item.state_id for item in incident.affected_states],
        "missing_evidence": missing,
        "complete": not missing and incident.status == "reverified",
        "causality_established": False,
    }


def bind_existing_evidence_reference(
    reference: EvidenceReference,
) -> IncidentEvidenceReference:
    """Adapt an existing StateWake evidence reference without copying its payload."""
    return IncidentEvidenceReference(
        kind=reference.kind,
        identity=reference.identity,
        digest=reference.digest,
        source=reference.source,
    )
