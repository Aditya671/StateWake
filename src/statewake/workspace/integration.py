"""Adapter binding existing StateWake ingestion to the workspace index."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from ..adapters.content_store import ContentAddressedArtifactStore
from ..adapters.evidence_ingestion import (
    JsonEvidenceReceiptStore,
    LocalEvidenceIngestionAdapter,
)
from ..domain.data_lifecycle import DataLifecycleDecision, DataLifecyclePolicy
from ..domain.evidence_receipt import ExternalEvidenceReceipt
from .analytical import AnalyticalQueryResult, DuckDBAnalyticalAdapter
from .csv_export import CsvExportResult, verify_csv, write_csv
from .errors import CorruptWorkspaceDatabaseError, UnsupportedWorkspaceSchemaError
from .json_export import JsonExportResult, verify_json, write_json
from .lifecycle import WorkspaceLifecycle, WorkspaceLifecycleResult
from .models import (
    WorkspaceIdentity,
    WorkspaceQueryPage,
    WorkspaceRecord,
    WorkspaceRecordIndexEntry,
    WorkspaceRecordQuery,
    WorkspaceRetention,
)
from .parquet_export import ParquetExportResult, verify_parquet, write_parquet
from .portable_bundle import (
    PortableBundleResult,
    verify_portable_bundle,
    write_portable_bundle,
)
from .projections import DatasetProjection
from .repository import StateWakeRepository
from .verification import WorkspaceVerificationReport, WorkspaceVerifier
from .xlsx_export import XlsxExportResult, verify_xlsx, write_xlsx


class WorkspaceIngestionAdapter:
    """Delegate evidence capture to StateWake and index the resulting receipt."""

    def __init__(self, workspace_root: Path, repository: StateWakeRepository) -> None:
        """Initialize the binding over existing canonical persistence components."""
        self._repository = repository
        self._receipt_store = JsonEvidenceReceiptStore(workspace_root / "receipts")
        self._lifecycle = WorkspaceLifecycle(workspace_root, repository)
        self._verifier = WorkspaceVerifier(workspace_root)
        self._analytical = DuckDBAnalyticalAdapter()
        self._ingestion = LocalEvidenceIngestionAdapter(
            ContentAddressedArtifactStore(workspace_root / "artifacts"),
            self._receipt_store,
        )

    def ingest_bytes(
        self,
        content: bytes,
        *,
        producer_type: str,
        producer_id: str,
        source_ref: str,
        captured_at: datetime,
        source_event_id: str | None = None,
        producer_version: str | None = None,
        run_id: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> WorkspaceRecord:
        """Capture bytes through StateWake and register the canonical receipt."""
        receipt = self._ingestion.ingest_bytes(
            content,
            producer_type=producer_type,
            producer_id=producer_id,
            source_ref=source_ref,
            captured_at=captured_at,
            source_event_id=source_event_id,
            producer_version=producer_version,
            run_id=run_id,
            metadata=dict(metadata or {}),
        )
        return self._index_receipt(receipt)

    def ingest_file(
        self,
        path: Path,
        *,
        producer_type: str,
        producer_id: str,
        captured_at: datetime,
        source_event_id: str | None = None,
        producer_version: str | None = None,
        run_id: str | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> WorkspaceRecord:
        """Capture a file through StateWake and register the canonical receipt."""
        receipt = self._ingestion.ingest_file(
            path,
            producer_type=producer_type,
            producer_id=producer_id,
            captured_at=captured_at,
            source_event_id=source_event_id,
            producer_version=producer_version,
            run_id=run_id,
            metadata=dict(metadata or {}),
        )
        return self._index_receipt(receipt)

    def verify(self, record: WorkspaceRecord) -> None:
        """Verify the canonical receipt and content through StateWake."""
        self._ingestion.verify(record.receipt)

    def verify_workspace(
        self,
        *,
        identity: WorkspaceIdentity,
        manifest_path: Path,
    ) -> WorkspaceVerificationReport:
        """Run a workspace-level integrity verification report."""
        try:
            snapshot = self._repository.integrity_snapshot()
        except (
            OSError,
            ValueError,
            UnsupportedWorkspaceSchemaError,
            CorruptWorkspaceDatabaseError,
        ) as exc:
            from .verification import WorkspaceVerificationIssue

            return WorkspaceVerificationReport(
                status="corrupt",
                issues=(
                    WorkspaceVerificationIssue(
                        "REPOSITORY_UNAVAILABLE",
                        "error",
                        f"workspace repository could not be verified: {exc}",
                    ),
                ),
            )
        return self._verifier.verify(
            identity=identity,
            manifest_path=manifest_path,
            repository_snapshot=snapshot,
        )

    def query(self, query: WorkspaceRecordQuery) -> WorkspaceQueryPage:
        """Query indexed history and hydrate results from canonical receipts."""
        entries, total_count = self._repository.query_records(query)
        records = tuple(self._hydrate(entry) for entry in entries)
        return WorkspaceQueryPage(
            records=records,
            total_count=total_count,
            limit=query.limit,
            offset=query.offset,
        )

    def project(self, query: WorkspaceRecordQuery) -> DatasetProjection:
        """Project one logical historical query into the stable dataset model."""
        return DatasetProjection.from_query_page(self.query(query))

    def query_parquet(
        self,
        parquet_path: Path,
        sql: str,
        *,
        parameters: tuple[object, ...] = (),
    ) -> AnalyticalQueryResult:
        """Query Parquet analytically without mutating workspace records."""
        return self._analytical.query_parquet(
            parquet_path,
            sql,
            parameters=parameters,
        )

    def snapshot_parquet(
        self,
        parquet_path: Path,
        output: Path,
        sql: str,
        *,
        parameters: tuple[object, ...] = (),
    ) -> Path:
        """Persist an explicit analytical snapshot outside authoritative storage."""
        return self._analytical.snapshot_parquet(
            parquet_path,
            output,
            sql,
            parameters=parameters,
        )

    def export_parquet(
        self,
        query: WorkspaceRecordQuery,
        output: Path,
        *,
        max_sensitivity: str | None = None,
        partition_by: tuple[str, ...] = (),
    ) -> ParquetExportResult:
        """Export one bounded historical query as canonical Parquet."""
        effective_query = _query_with_export_ceiling(query, max_sensitivity)
        projection = self.project(effective_query)
        query_definition = _query_definition(effective_query)
        result = write_parquet(
            projection,
            output,
            schema_version="1",
            disclosure_max_sensitivity=effective_query.max_sensitivity or "restricted",
            query_definition=query_definition,
            partition_by=partition_by,
        )
        verify_parquet(
            result.output_path,
            expected_rows=result.row_count,
            expected_schema_version="1",
        )
        self._repository.record_export(
            export_id=result.export_id,
            format_record="parquet",
            created_at=datetime.now(UTC).isoformat(),
            query_definition_json=json.dumps(
                query_definition,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            disclosure_max_sensitivity=result.disclosure_max_sensitivity,
            source_schema_version=result.schema_version,
            output_path=str(result.output_path),
            output_digest=result.output_digest,
            row_count=result.row_count,
        )
        return result

    def export_csv(
        self,
        query: WorkspaceRecordQuery,
        output: Path,
        *,
        max_sensitivity: str | None = None,
    ) -> CsvExportResult:
        """Export one bounded historical query page as deterministic CSV."""
        effective_query = _query_with_export_ceiling(query, max_sensitivity)
        query_definition = _query_definition(effective_query)
        projection = self.project(effective_query)
        result = write_csv(
            projection.records,
            output,
            schema_version="1",
            disclosure_max_sensitivity=effective_query.max_sensitivity or "restricted",
            query_definition=query_definition,
        )
        verify_csv(
            result.output_path,
            expected_rows=result.row_count,
            expected_schema_version="1",
        )
        self._repository.record_export(
            export_id=result.export_id,
            format_record="csv",
            created_at=datetime.now(UTC).isoformat(),
            query_definition_json=json.dumps(
                query_definition,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            disclosure_max_sensitivity=result.disclosure_max_sensitivity,
            source_schema_version=result.schema_version,
            output_path=str(result.output_path),
            output_digest=result.output_digest,
            row_count=result.row_count,
        )
        return result

    def export_xlsx(
        self,
        query: WorkspaceRecordQuery,
        output: Path,
        *,
        max_sensitivity: str | None = None,
    ) -> XlsxExportResult:
        """Export one bounded historical query as human-friendly XLSX."""
        effective_query = _query_with_export_ceiling(query, max_sensitivity)
        query_definition = _query_definition(effective_query)
        projection = self.project(effective_query)
        result = write_xlsx(
            projection.records,
            output,
            schema_version="1",
            disclosure_max_sensitivity=effective_query.max_sensitivity or "restricted",
            query_definition=query_definition,
        )
        verify_xlsx(
            result.output_path,
            expected_rows=result.row_count,
            expected_schema_version="1",
        )
        self._repository.record_export(
            export_id=result.export_id,
            format_record="xlsx",
            created_at=datetime.now(UTC).isoformat(),
            query_definition_json=json.dumps(
                query_definition,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            disclosure_max_sensitivity=result.disclosure_max_sensitivity,
            source_schema_version=result.schema_version,
            output_path=str(result.output_path),
            output_digest=result.output_digest,
            row_count=result.row_count,
        )
        return result

    def export_json(
        self,
        query: WorkspaceRecordQuery,
        output: Path,
        *,
        max_sensitivity: str | None = None,
    ) -> JsonExportResult:
        """Export one bounded historical query as deterministic JSON."""
        effective_query = _query_with_export_ceiling(query, max_sensitivity)
        query_definition = _query_definition(effective_query)
        projection = self.project(effective_query)
        result = write_json(
            projection,
            output,
            schema_version="1",
            disclosure_max_sensitivity=effective_query.max_sensitivity or "restricted",
            query_definition=query_definition,
        )
        verify_json(
            result.output_path,
            expected_rows=result.row_count,
            expected_schema_version="1",
        )
        self._repository.record_export(
            export_id=result.export_id,
            format_record="json",
            created_at=datetime.now(UTC).isoformat(),
            query_definition_json=json.dumps(
                query_definition,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            disclosure_max_sensitivity=result.disclosure_max_sensitivity,
            source_schema_version=result.schema_version,
            output_path=str(result.output_path),
            output_digest=result.output_digest,
            row_count=result.row_count,
        )
        return result

    def export_portable_bundle(
        self,
        query: WorkspaceRecordQuery,
        output: Path,
        *,
        max_sensitivity: str | None = None,
    ) -> PortableBundleResult:
        """Export one bounded historical query as a portable dataset bundle."""
        effective_query = _query_with_export_ceiling(query, max_sensitivity)
        query_definition = _query_definition(effective_query)
        page = self.query(effective_query)
        projection = DatasetProjection.from_query_page(page)
        result = write_portable_bundle(
            projection,
            page.records,
            output,
            workspace_id=self._repository.get_workspace_identity().workspace_id,
            schema_version="1",
            disclosure_max_sensitivity=effective_query.max_sensitivity or "restricted",
            query_definition=query_definition,
            created_at=datetime.now(UTC),
        )
        verify_portable_bundle(
            result.output_path,
            expected_rows=result.row_count,
            expected_schema_version="1",
            expected_workspace_id=self._repository.get_workspace_identity().workspace_id,
        )
        self._repository.record_export(
            export_id=result.export_id,
            format_record="portable_bundle",
            created_at=datetime.now(UTC).isoformat(),
            query_definition_json=json.dumps(
                query_definition,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            disclosure_max_sensitivity=result.disclosure_max_sensitivity,
            source_schema_version=result.schema_version,
            output_path=str(result.output_path),
            output_digest=result.output_digest,
            row_count=result.row_count,
        )
        return result

    def apply_retention(
        self,
        record_id: str,
        policy: DataLifecyclePolicy,
        *,
        legal_hold: bool = False,
        now: datetime | None = None,
    ) -> WorkspaceRetention:
        """Apply durable record retention and legal-hold semantics."""
        return self._lifecycle.apply_retention(
            record_id, policy, legal_hold=legal_hold, now=now
        )

    def evaluate_lifecycle(
        self,
        record_id: str,
        policy: DataLifecyclePolicy,
        *,
        now: datetime | None = None,
    ) -> DataLifecycleDecision:
        """Evaluate one record against its lifecycle requirements."""
        return self._lifecycle.evaluate_record(record_id, policy, now=now)

    def delete_expired(
        self,
        record_id: str,
        *,
        now: datetime | None = None,
        reason: str = "retention expired",
    ) -> WorkspaceLifecycleResult:
        """Delete one expired record payload through the canonical artifact adapter."""
        return self._lifecycle.delete_expired_record(record_id, now=now, reason=reason)

    def apply_export_retention(
        self,
        export_id: str,
        policy: DataLifecyclePolicy,
        *,
        sensitivity: str = "internal",
        legal_hold: bool = False,
        now: datetime | None = None,
    ) -> WorkspaceRetention:
        """Apply durable lifecycle requirements to one workspace-controlled export."""
        return self._lifecycle.apply_export_retention(
            export_id, policy, sensitivity=sensitivity, legal_hold=legal_hold, now=now
        )

    def delete_expired_export(
        self,
        export_id: str,
        *,
        now: datetime | None = None,
        reason: str = "retention expired",
    ) -> WorkspaceLifecycleResult:
        """Delete one expired workspace-controlled export."""
        return self._lifecycle.delete_expired_export(export_id, now=now, reason=reason)

    def get_record(self, record_id: str) -> WorkspaceRecord | None:
        """Return one historical record by deterministic record identity."""
        page = self.query(WorkspaceRecordQuery(record_id=record_id, limit=1))
        return page.records[0] if page.records else None

    def query_run(
        self, run_id: str, *, limit: int = 100, offset: int = 0
    ) -> WorkspaceQueryPage:
        """Return historical records associated with one run identity."""
        return self.query(
            WorkspaceRecordQuery(run_id=run_id, limit=limit, offset=offset)
        )

    def query_event(
        self, source_event_id: str, *, limit: int = 100, offset: int = 0
    ) -> WorkspaceQueryPage:
        """Return historical records associated with one source event identity."""
        return self.query(
            WorkspaceRecordQuery(
                source_event_id=source_event_id, limit=limit, offset=offset
            )
        )

    def _index_receipt(self, receipt: ExternalEvidenceReceipt) -> WorkspaceRecord:
        """Project one existing receipt into the workspace's operational index."""
        record = WorkspaceRecord(
            record_id=receipt.receipt_id,
            receipt=receipt,
            created_at=receipt.captured_at,
        )
        self._repository.index_record(record)
        return record

    def _hydrate(self, entry: WorkspaceRecordIndexEntry) -> WorkspaceRecord:
        """Hydrate an indexed row from its authoritative persisted receipt."""
        receipt = self._receipt_store.get(entry.receipt_id)
        expected = {
            "record_id": entry.record_id,
            "artifact_digest": entry.artifact_digest,
            "artifact_size": entry.artifact_size,
            "producer_id": entry.producer_id,
            "producer_type": entry.producer_type,
            "producer_version": entry.producer_version,
            "source_ref": entry.source_ref,
            "source_event_id": entry.source_event_id,
            "run_id": entry.run_id,
            "captured_at": entry.captured_at,
        }
        actual = {
            "record_id": receipt.receipt_id,
            "artifact_digest": receipt.artifact_digest,
            "artifact_size": receipt.artifact_size,
            "producer_id": receipt.producer_id,
            "producer_type": receipt.producer_type,
            "producer_version": receipt.producer_version,
            "source_ref": receipt.source_ref,
            "source_event_id": receipt.source_event_id,
            "run_id": receipt.run_id,
            "captured_at": receipt.captured_at.astimezone(entry.captured_at.tzinfo),
        }
        if expected != actual:
            raise ValueError(
                f"workspace index does not match persisted receipt {entry.receipt_id}."
            )
        return WorkspaceRecord(
            record_id=entry.record_id,
            receipt=receipt,
            created_at=entry.created_at,
            sensitivity=entry.sensitivity,
            policy_id=entry.policy_id,
            verification_status=entry.verification_status,
            reliability_state=entry.reliability_state,
        )


def _query_with_export_ceiling(
    query: WorkspaceRecordQuery, max_sensitivity: str | None
) -> WorkspaceRecordQuery:
    """Apply an export-only disclosure ceiling without weakening query filters."""
    if max_sensitivity is None or query.max_sensitivity == max_sensitivity:
        return query
    if query.max_sensitivity is not None:
        raise ValueError("query and export sensitivity ceilings must match")
    return WorkspaceRecordQuery(
        record_id=query.record_id,
        run_id=query.run_id,
        source_event_id=query.source_event_id,
        producer_id=query.producer_id,
        verification_status=query.verification_status,
        reliability_state=query.reliability_state,
        sensitivity=query.sensitivity,
        max_sensitivity=max_sensitivity,
        captured_from=query.captured_from,
        captured_to=query.captured_to,
        limit=query.limit,
        offset=query.offset,
    )


def _query_definition(query: WorkspaceRecordQuery) -> dict[str, object]:
    """Serialize the stable query definition associated with an export."""
    return {
        "record_id": query.record_id,
        "run_id": query.run_id,
        "source_event_id": query.source_event_id,
        "producer_id": query.producer_id,
        "verification_status": query.verification_status,
        "reliability_state": query.reliability_state,
        "sensitivity": query.sensitivity,
        "max_sensitivity": query.max_sensitivity,
        "captured_from": query.captured_from.isoformat()
        if query.captured_from
        else None,
        "captured_to": query.captured_to.isoformat() if query.captured_to else None,
        "limit": query.limit,
        "offset": query.offset,
    }


__all__ = ["WorkspaceIngestionAdapter"]
