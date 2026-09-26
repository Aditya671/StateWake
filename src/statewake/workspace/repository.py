"""Repository contract for durable StateWake workspace metadata."""

from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Protocol

from ..domain.data_lifecycle import DeletionRecord
from .models import (
    WorkspaceExport,
    WorkspaceIdentity,
    WorkspaceRecord,
    WorkspaceRecordIndexEntry,
    WorkspaceRecordQuery,
    WorkspaceRetention,
)


class WorkspaceTransaction(AbstractContextManager["WorkspaceTransaction"], Protocol):
    """Context manager representing one repository transaction."""

    def set_workspace_metadata(
        self, identity: WorkspaceIdentity, statewake_version: str
    ) -> None:
        """Atomically persist workspace identity and package metadata."""
        ...


@dataclass(frozen=True, slots=True)
class WorkspaceIntegritySnapshot:
    """Contain the read-only durable metadata needed for workspace verification."""

    records: tuple[WorkspaceRecordIndexEntry, ...]
    run_ids: frozenset[str]
    relationship_rows: tuple[tuple[str, str, str], ...]
    state_transition_subject_ids: frozenset[str]
    retention_object_ids: frozenset[str]
    deletion_records: tuple[DeletionRecord, ...]
    exports: tuple[WorkspaceExport, ...]


class StateWakeRepository(Protocol):
    """Persistence boundary for the workspace operational index."""

    def initialize(self) -> None:
        """Create or validate the repository schema."""
        ...

    def transaction(self) -> WorkspaceTransaction:
        """Return a transaction context for atomic metadata changes."""
        ...

    def index_record(self, record: WorkspaceRecord) -> None:
        """Atomically register an existing StateWake receipt in the index."""
        ...

    def get_workspace_identity(self) -> WorkspaceIdentity:
        """Return the persisted workspace identity."""
        ...

    def query_records(
        self, query: WorkspaceRecordQuery
    ) -> tuple[tuple[WorkspaceRecordIndexEntry, ...], int]:
        """Return one bounded deterministic page of indexed records and its total."""
        ...

    def upsert_retention(
        self,
        *,
        object_id: str,
        policy_id: str,
        sensitivity: str,
        retain_until: str | None,
        legal_hold: bool,
    ) -> None:
        """Persist one retention requirement and legal-hold state."""
        ...

    def get_retention(self, object_id: str) -> WorkspaceRetention | None:
        """Return one persisted retention requirement when registered."""
        ...

    def record_deletion(self, deletion: DeletionRecord) -> None:
        """Persist one payload-free deletion tombstone."""
        ...

    def get_deletion(self, object_id: str) -> DeletionRecord | None:
        """Return one payload-free deletion tombstone when present."""
        ...

    def get_export(self, export_id: str) -> WorkspaceExport | None:
        """Return one persisted export record when present."""
        ...

    def integrity_snapshot(self) -> WorkspaceIntegritySnapshot:
        """Return a read-only snapshot of durable workspace references."""
        ...

    def list_exports(self, *, limit: int = 1000) -> tuple[WorkspaceExport, ...]:
        """Return recent export metadata in deterministic order."""
        ...

    def record_export(
        self,
        *,
        export_id: str,
        format_record: str = "parquet",
        created_at: str,
        query_definition_json: str,
        disclosure_max_sensitivity: str,
        source_schema_version: str,
        output_path: str,
        output_digest: str,
        row_count: int,
    ) -> None:
        """Persist one completed analytical export record."""
        ...


__all__ = ["StateWakeRepository", "WorkspaceIntegritySnapshot", "WorkspaceTransaction"]
