"""Typed models for the StateWake workspace foundation and integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from ..domain.evidence_receipt import ExternalEvidenceReceipt


@dataclass(frozen=True, slots=True)
class WorkspaceIdentity:
    """Identify one durable StateWake workspace and its schema contract."""

    workspace_id: str
    created_at: str
    schema_version: str
    statewake_public_api_contract_version: str

    def __post_init__(self) -> None:
        """Validate required workspace identity fields."""
        for field_name in (
            "workspace_id",
            "created_at",
            "schema_version",
            "statewake_public_api_contract_version",
        ):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} must not be blank.")


@dataclass(frozen=True, slots=True)
class WorkspaceRecord:
    """Represent one evidence receipt registered in the workspace index."""

    record_id: str
    receipt: ExternalEvidenceReceipt
    created_at: datetime
    sensitivity: str = "internal"
    policy_id: str = "default"
    verification_status: str | None = None
    reliability_state: str | None = None

    def __post_init__(self) -> None:
        """Validate stable record identity and index metadata."""
        if not self.record_id.strip():
            raise ValueError("record_id must not be blank.")
        if self.record_id != self.receipt.receipt_id:
            raise ValueError("record_id must match receipt_id.")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware.")
        if not self.sensitivity.strip():
            raise ValueError("sensitivity must not be blank.")
        if not self.policy_id.strip():
            raise ValueError("policy_id must not be blank.")

    @property
    def receipt_id(self) -> str:
        """Return the canonical receipt identity."""
        return self.receipt.receipt_id

    @property
    def artifact_digest(self) -> str:
        """Return the content-addressed artifact digest."""
        return self.receipt.artifact_digest

    @property
    def artifact_size(self) -> int:
        """Return the captured artifact size."""
        return self.receipt.artifact_size

    @property
    def producer_id(self) -> str:
        """Return the evidence producer identity."""
        return self.receipt.producer_id

    @property
    def producer_type(self) -> str:
        """Return the evidence producer type."""
        return self.receipt.producer_type

    @property
    def producer_version(self) -> str | None:
        """Return the producer version when supplied."""
        return self.receipt.producer_version

    @property
    def source_ref(self) -> str:
        """Return the source reference carried by the receipt."""
        return self.receipt.source_ref

    @property
    def source_event_id(self) -> str | None:
        """Return the producer event identity when supplied."""
        return self.receipt.source_event_id

    @property
    def run_id(self) -> str | None:
        """Return the associated run identity when supplied."""
        return self.receipt.run_id

    @property
    def captured_at(self) -> datetime:
        """Return the source capture timestamp."""
        return self.receipt.captured_at

    @property
    def metadata(self) -> Mapping[str, str]:
        """Return the receipt metadata without exposing a mutable index copy."""
        return self.receipt.metadata


@dataclass(frozen=True, slots=True)
class WorkspaceRetention:
    """Represent durable retention metadata for one workspace object."""

    object_id: str
    policy_id: str
    sensitivity: str
    retain_until: str | None
    legal_hold: bool


@dataclass(frozen=True, slots=True)
class WorkspaceExport:
    """Represent persisted metadata for one completed workspace export."""

    export_id: str
    format: str
    created_at: str
    query_definition_json: str
    disclosure_max_sensitivity: str
    source_schema_version: str
    output_path: str
    output_digest: str | None
    row_count: int | None


@dataclass(frozen=True, slots=True)
class WorkspaceRecordQuery:
    """Bounded filters for deterministic historical workspace queries."""

    record_id: str | None = None
    run_id: str | None = None
    source_event_id: str | None = None
    producer_id: str | None = None
    verification_status: str | None = None
    reliability_state: str | None = None
    sensitivity: str | None = None
    max_sensitivity: str | None = None
    captured_from: datetime | None = None
    captured_to: datetime | None = None
    limit: int = 100
    offset: int = 0

    def __post_init__(self) -> None:
        """Validate query bounds, timestamps, and explicit filters."""
        for field_name in (
            "record_id",
            "run_id",
            "source_event_id",
            "producer_id",
            "verification_status",
            "reliability_state",
            "sensitivity",
            "max_sensitivity",
        ):
            value = getattr(self, field_name)
            if value is not None and not value.strip():
                raise ValueError(f"{field_name} must not be blank when provided.")
        if self.captured_from is not None and self.captured_from.tzinfo is None:
            raise ValueError("captured_from must be timezone-aware.")
        if self.captured_to is not None and self.captured_to.tzinfo is None:
            raise ValueError("captured_to must be timezone-aware.")
        if (
            self.captured_from is not None
            and self.captured_to is not None
            and self.captured_from >= self.captured_to
        ):
            raise ValueError("captured_from must be earlier than captured_to.")
        if self.limit < 1 or self.limit > 1000:
            raise ValueError("limit must be between 1 and 1000.")
        if self.offset < 0:
            raise ValueError("offset must be non-negative.")


@dataclass(frozen=True, slots=True)
class WorkspaceRecordIndexEntry:
    """Represent one typed row returned by the workspace operational index."""

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


@dataclass(frozen=True, slots=True)
class WorkspaceQueryPage:
    """Contain one deterministic, bounded page of workspace records."""

    records: tuple[WorkspaceRecord, ...]
    total_count: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        """Return whether more records exist after this page."""
        return self.offset + len(self.records) < self.total_count

    @property
    def next_offset(self) -> int | None:
        """Return the offset for the next page, when one exists."""
        if not self.has_more:
            return None
        return self.offset + self.limit


__all__ = [
    "WorkspaceIdentity",
    "WorkspaceQueryPage",
    "WorkspaceRecord",
    "WorkspaceRecordIndexEntry",
    "WorkspaceRecordQuery",
    "WorkspaceRetention",
    "WorkspaceExport",
]
