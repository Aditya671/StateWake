"""Stable typed projections for StateWake analytical datasets."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

from .models import WorkspaceQueryPage, WorkspaceRecord

PROJECTION_SCHEMA_VERSION = "1"


def _datetime_value(value: datetime) -> str:
    """Serialize an aware datetime as canonical UTC ISO-8601 text."""
    if value.tzinfo is None:
        raise ValueError("datetime values must be timezone-aware.")
    return value.astimezone(UTC).isoformat()


def _optional_datetime_value(value: datetime | None) -> str | None:
    """Serialize an optional aware datetime while preserving null explicitly."""
    if value is None:
        return None
    return _datetime_value(value)


@dataclass(frozen=True, slots=True)
class NormalizedRecordProjection:
    """Represent one normalized StateWake record for analytical export."""

    record_id: str
    receipt_id: str
    artifact_digest: str
    artifact_size: int
    producer_id: str
    producer_type: str
    producer_version: str | None
    source_ref: str
    source_event_id: str | None
    run_id: str | None
    captured_at: datetime
    sensitivity: str
    policy_id: str
    verification_status: str | None
    reliability_state: str | None
    created_at: datetime

    @classmethod
    def from_record(cls, record: WorkspaceRecord) -> NormalizedRecordProjection:
        """Build a projection from the canonical workspace record."""
        return cls(
            record_id=record.record_id,
            receipt_id=record.receipt_id,
            artifact_digest=record.artifact_digest,
            artifact_size=record.artifact_size,
            producer_id=record.producer_id,
            producer_type=record.producer_type,
            producer_version=record.producer_version,
            source_ref=record.source_ref,
            source_event_id=record.source_event_id,
            run_id=record.run_id,
            captured_at=record.captured_at,
            sensitivity=record.sensitivity,
            policy_id=record.policy_id,
            verification_status=record.verification_status,
            reliability_state=record.reliability_state,
            created_at=record.created_at,
        )

    def to_dict(self) -> dict[str, object]:
        """Return the canonical projection representation."""
        return {
            "record_id": self.record_id,
            "receipt_id": self.receipt_id,
            "artifact_digest": self.artifact_digest,
            "artifact_size": self.artifact_size,
            "producer_id": self.producer_id,
            "producer_type": self.producer_type,
            "producer_version": self.producer_version,
            "source_ref": self.source_ref,
            "source_event_id": self.source_event_id,
            "run_id": self.run_id,
            "captured_at": _datetime_value(self.captured_at),
            "sensitivity": self.sensitivity,
            "policy_id": self.policy_id,
            "verification_status": self.verification_status,
            "reliability_state": self.reliability_state,
            "created_at": _datetime_value(self.created_at),
        }


@dataclass(frozen=True, slots=True)
class RelationshipProjection:
    """Represent one normalized workspace relationship."""

    source_id: str
    target_id: str
    relationship_type: str
    created_at: datetime

    def to_dict(self) -> dict[str, object]:
        """Return the canonical projection representation."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relationship_type": self.relationship_type,
            "created_at": _datetime_value(self.created_at),
        }


@dataclass(frozen=True, slots=True)
class RunProjection:
    """Represent one normalized workspace run."""

    run_id: str
    producer_id: str
    producer_type: str
    producer_version: str | None
    started_at: datetime
    finished_at: datetime | None
    status: str
    metadata: Mapping[str, str] | None

    def to_dict(self) -> dict[str, object]:
        """Return the canonical projection representation."""
        return {
            "run_id": self.run_id,
            "producer_id": self.producer_id,
            "producer_type": self.producer_type,
            "producer_version": self.producer_version,
            "started_at": _datetime_value(self.started_at),
            "finished_at": _optional_datetime_value(self.finished_at),
            "status": self.status,
            "metadata": (
                None if self.metadata is None else dict(sorted(self.metadata.items()))
            ),
        }


@dataclass(frozen=True, slots=True)
class StateTransitionProjection:
    """Represent one normalized reliability state transition."""

    transition_id: str
    subject_id: str
    from_state: str | None
    to_state: str
    previous_digest: str | None
    current_digest: str | None
    occurred_at: datetime

    def to_dict(self) -> dict[str, object]:
        """Return the canonical projection representation."""
        return {
            "transition_id": self.transition_id,
            "subject_id": self.subject_id,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "previous_digest": self.previous_digest,
            "current_digest": self.current_digest,
            "occurred_at": _datetime_value(self.occurred_at),
        }


@dataclass(frozen=True, slots=True)
class RetentionProjection:
    """Represent one normalized retention decision record."""

    object_id: str
    policy_id: str
    sensitivity: str
    retain_until: datetime | None
    legal_hold: bool

    def to_dict(self) -> dict[str, object]:
        """Return the canonical projection representation."""
        return {
            "object_id": self.object_id,
            "policy_id": self.policy_id,
            "sensitivity": self.sensitivity,
            "retain_until": _optional_datetime_value(self.retain_until),
            "legal_hold": self.legal_hold,
        }


@dataclass(frozen=True, slots=True)
class DeletionProjection:
    """Represent one payload-free deletion-history record."""

    object_id: str
    digest: str
    sensitivity: str
    deleted_at: datetime
    policy_id: str
    reason: str

    def to_dict(self) -> dict[str, object]:
        """Return the canonical projection representation."""
        return {
            "object_id": self.object_id,
            "digest": self.digest,
            "sensitivity": self.sensitivity,
            "deleted_at": _datetime_value(self.deleted_at),
            "policy_id": self.policy_id,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class DatasetProjection:
    """Contain stable typed collections used by later export formats."""

    records: tuple[NormalizedRecordProjection, ...]
    relationships: tuple[RelationshipProjection, ...] = ()
    runs: tuple[RunProjection, ...] = ()
    state_transitions: tuple[StateTransitionProjection, ...] = ()
    retention: tuple[RetentionProjection, ...] = ()
    deletions: tuple[DeletionProjection, ...] = ()
    schema_version: str = PROJECTION_SCHEMA_VERSION

    @classmethod
    def from_query_page(cls, page: WorkspaceQueryPage) -> DatasetProjection:
        """Project one historical query page without altering query semantics."""
        return cls(
            records=tuple(
                NormalizedRecordProjection.from_record(record)
                for record in page.records
            )
        )

    def to_dict(self) -> dict[str, object]:
        """Return the complete canonical projection representation."""
        return {
            "schema_version": self.schema_version,
            "records": [record.to_dict() for record in self.records],
            "relationships": [item.to_dict() for item in self.relationships],
            "runs": [item.to_dict() for item in self.runs],
            "state_transitions": [item.to_dict() for item in self.state_transitions],
            "retention": [item.to_dict() for item in self.retention],
            "deletions": [item.to_dict() for item in self.deletions],
        }


__all__ = [
    "DATASET_PROJECTION_SCHEMA_VERSION",
    "DatasetProjection",
    "DeletionProjection",
    "NormalizedRecordProjection",
    "RelationshipProjection",
    "RetentionProjection",
    "RunProjection",
    "StateTransitionProjection",
]

# Backward-compatible named constant for callers that prefer the longer form.
DATASET_PROJECTION_SCHEMA_VERSION = PROJECTION_SCHEMA_VERSION
