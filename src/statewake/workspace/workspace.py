"""Durable StateWake workspace foundation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ..domain.data_lifecycle import DataLifecycleDecision, DataLifecyclePolicy
from ..services.persistence import atomic_write_text
from .analytical import AnalyticalQueryResult
from .configuration import WorkspaceConfiguration
from .csv_export import CsvExportResult
from .integration import WorkspaceIngestionAdapter
from .json_export import JsonExportResult
from .lifecycle import WorkspaceLifecycleResult
from .models import (
    WorkspaceExport,
    WorkspaceIdentity,
    WorkspaceQueryPage,
    WorkspaceRecord,
    WorkspaceRecordQuery,
    WorkspaceRetention,
)
from .operations import (
    WorkspaceDiagnostics,
    WorkspaceDiagnosticsCollector,
    WorkspaceOperationLock,
    WorkspaceStorageReport,
)
from .parquet_export import ParquetExportResult
from .portable_bundle import PortableBundleResult
from .projections import DatasetProjection
from .repository import StateWakeRepository
from .sqlite_repository import SqliteWorkspaceRepository
from .verification import WorkspaceVerificationReport
from .xlsx_export import XlsxExportResult

_MANIFEST_INDENT = 2
_MANIFEST_SCHEMA_VERSION = "1"


class WorkspaceError(Exception):
    """Base class for workspace foundation failures."""


class WorkspaceManifestError(WorkspaceError):
    """Raised when a workspace manifest is missing or invalid."""


class WorkspaceSchemaError(WorkspaceError):
    """Raised when a workspace uses an unsupported schema version."""


class StateWakeWorkspace:
    """Own the durable filesystem boundary for one StateWake workspace."""

    def __init__(
        self,
        configuration: WorkspaceConfiguration,
        identity: WorkspaceIdentity,
        repository: StateWakeRepository | None = None,
    ) -> None:
        """Initialize an already-created workspace from its validated identity."""
        self._configuration = configuration
        self._identity = identity
        self._repository = repository or SqliteWorkspaceRepository(
            configuration.database_path
        )
        self._ingestion = WorkspaceIngestionAdapter(
            configuration.root, self._repository
        )
        self._closed = False
        self._operation_lock_path = (
            configuration.lock_root / "workspace.operations.lock"
        )
        self._diagnostics = WorkspaceDiagnosticsCollector(
            configuration.root, self._repository
        )

    @classmethod
    def open(
        cls,
        root: Path | str = Path(".statewake"),
        *,
        repository: StateWakeRepository | None = None,
    ) -> StateWakeWorkspace:
        """Create or reopen a workspace at the supplied filesystem root."""
        configuration = cls._configuration_for(root)
        cls._initialize_directories(configuration)
        operation_lock_path = configuration.lock_root / "workspace.operations.lock"
        with WorkspaceOperationLock(operation_lock_path):
            if configuration.manifest_path.exists():
                identity = cls._read_manifest(configuration)
            else:
                identity = cls._create_identity(configuration)
                cls._write_manifest(configuration, identity)
            workspace = cls(configuration, identity, repository=repository)
            workspace._repository.initialize()
            with workspace._repository.transaction() as transaction:
                transaction.set_workspace_metadata(identity, _statewake_version())
            workspace.recover()
        return workspace

    @property
    def configuration(self) -> WorkspaceConfiguration:
        """Return immutable workspace configuration."""
        return self._configuration

    @property
    def identity(self) -> WorkspaceIdentity:
        """Return immutable workspace identity."""
        return self._identity

    @property
    def root(self) -> Path:
        """Return the resolved workspace root."""
        return self._configuration.root

    @property
    def closed(self) -> bool:
        """Return whether the workspace has been closed."""
        return self._closed

    @property
    def repository(self) -> StateWakeRepository:
        """Return the durable operational-index repository."""
        return self._repository

    def operation_lock(self, *, timeout: float = 30.0) -> WorkspaceOperationLock:
        """Return the bounded mutation lock for this workspace."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        return WorkspaceOperationLock(self._operation_lock_path, timeout=timeout)

    def diagnostics(self) -> WorkspaceDiagnostics:
        """Return operational health, storage, and export diagnostics."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        verification = self._ingestion.verify_workspace(
            identity=self.identity,
            manifest_path=self.configuration.manifest_path,
        )
        return self._diagnostics.collect(verification)

    def storage_report(self) -> WorkspaceStorageReport:
        """Return workspace-owned regular-file storage usage."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        return self._diagnostics.storage()

    def export_history(self, *, limit: int = 1000) -> tuple[WorkspaceExport, ...]:
        """Return completed export metadata in deterministic order."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        return self._repository.list_exports(limit=limit)

    def ingest(
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
        metadata: dict[str, str] | None = None,
    ) -> WorkspaceRecord:
        """Capture bytes through the existing StateWake ingestion contract."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        with self.operation_lock():
            return self._ingestion.ingest_bytes(
                content,
                producer_type=producer_type,
                producer_id=producer_id,
                source_ref=source_ref,
                captured_at=captured_at,
                source_event_id=source_event_id,
                producer_version=producer_version,
                run_id=run_id,
                metadata=metadata,
            )

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
        metadata: dict[str, str] | None = None,
    ) -> WorkspaceRecord:
        """Capture a file through the existing StateWake ingestion contract."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        with self.operation_lock():
            return self._ingestion.ingest_file(
                path,
                producer_type=producer_type,
                producer_id=producer_id,
                captured_at=captured_at,
                source_event_id=source_event_id,
                producer_version=producer_version,
                run_id=run_id,
                metadata=metadata,
            )

    def verify(
        self, record: WorkspaceRecord | None = None
    ) -> None | WorkspaceVerificationReport:
        """Verify one record or the complete workspace when no record is supplied."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        if record is not None:
            self._ingestion.verify(record)
            return None
        return self._ingestion.verify_workspace(
            identity=self.identity,
            manifest_path=self.configuration.manifest_path,
        )

    def query(self, query: WorkspaceRecordQuery) -> WorkspaceQueryPage:
        """Return a bounded, deterministic page of historical workspace records."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        return self._ingestion.query(query)

    def project(self, query: WorkspaceRecordQuery) -> DatasetProjection:
        """Project one historical query into the stable analytical dataset model."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        return self._ingestion.project(query)

    def query_parquet(
        self,
        parquet_path: Path,
        sql: str,
        *,
        parameters: tuple[object, ...] = (),
    ) -> AnalyticalQueryResult:
        """Query an exported Parquet dataset through optional DuckDB access."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        return self._ingestion.query_parquet(
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
        """Create an explicit analytical Parquet snapshot."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        return self._ingestion.snapshot_parquet(
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
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        with self.operation_lock():
            return self._ingestion.export_parquet(
                query,
                output,
                max_sensitivity=max_sensitivity,
                partition_by=partition_by,
            )

    def export_csv(
        self,
        query: WorkspaceRecordQuery,
        output: Path,
        *,
        max_sensitivity: str | None = None,
    ) -> CsvExportResult:
        """Export one bounded historical query as deterministic CSV."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        with self.operation_lock():
            return self._ingestion.export_csv(
                query, output, max_sensitivity=max_sensitivity
            )

    def export_xlsx(
        self,
        query: WorkspaceRecordQuery,
        output: Path,
        *,
        max_sensitivity: str | None = None,
    ) -> XlsxExportResult:
        """Export one bounded historical query as human-friendly XLSX."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        with self.operation_lock():
            return self._ingestion.export_xlsx(
                query, output, max_sensitivity=max_sensitivity
            )

    def export_json(
        self,
        query: WorkspaceRecordQuery,
        output: Path,
        *,
        max_sensitivity: str | None = None,
    ) -> JsonExportResult:
        """Export one bounded historical query as deterministic JSON."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        with self.operation_lock():
            return self._ingestion.export_json(
                query, output, max_sensitivity=max_sensitivity
            )

    def export_portable_bundle(
        self,
        query: WorkspaceRecordQuery,
        output: Path,
        *,
        max_sensitivity: str | None = None,
    ) -> PortableBundleResult:
        """Export one bounded historical query as a portable dataset bundle."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        with self.operation_lock():
            return self._ingestion.export_portable_bundle(
                query, output, max_sensitivity=max_sensitivity
            )

    def apply_retention(
        self,
        record_id: str,
        policy: DataLifecyclePolicy,
        *,
        legal_hold: bool = False,
        now: datetime | None = None,
    ) -> WorkspaceRetention:
        """Apply durable record retention and legal-hold semantics."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        with self.operation_lock():
            return self._ingestion.apply_retention(
                record_id, policy, legal_hold=legal_hold, now=now
            )

    def delete_expired(
        self,
        record_id: str,
        *,
        now: datetime | None = None,
        reason: str = "retention expired",
    ) -> WorkspaceLifecycleResult:
        """Delete one expired record payload through the canonical artifact adapter."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        with self.operation_lock():
            return self._ingestion.delete_expired(record_id, now=now, reason=reason)

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
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        with self.operation_lock():
            return self._ingestion.apply_export_retention(
                export_id,
                policy,
                sensitivity=sensitivity,
                legal_hold=legal_hold,
                now=now,
            )

    def delete_expired_export(
        self,
        export_id: str,
        *,
        now: datetime | None = None,
        reason: str = "retention expired",
    ) -> WorkspaceLifecycleResult:
        """Delete one expired workspace-controlled export."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        with self.operation_lock():
            return self._ingestion.delete_expired_export(
                export_id, now=now, reason=reason
            )

    def evaluate_lifecycle(
        self,
        record_id: str,
        policy: DataLifecyclePolicy,
        *,
        now: datetime | None = None,
    ) -> DataLifecycleDecision:
        """Evaluate one record against its lifecycle requirements."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        return self._ingestion.evaluate_lifecycle(record_id, policy, now=now)

    def get_record(self, record_id: str) -> WorkspaceRecord | None:
        """Return one historical record by deterministic record identity."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        return self._ingestion.get_record(record_id)

    def query_run(
        self, run_id: str, *, limit: int = 100, offset: int = 0
    ) -> WorkspaceQueryPage:
        """Return historical records for one run identity."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        return self._ingestion.query_run(run_id, limit=limit, offset=offset)

    def query_event(
        self, source_event_id: str, *, limit: int = 100, offset: int = 0
    ) -> WorkspaceQueryPage:
        """Return historical records for one source event identity."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        return self._ingestion.query_event(source_event_id, limit=limit, offset=offset)

    def recover(self) -> None:
        """Validate durable state and remove stale workspace temporary files."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        self._repository.initialize()
        self._recover_temporary_files()

    def close(self) -> None:
        """Close the workspace handle without deleting durable state."""
        self._closed = True

    def _recover_temporary_files(self) -> None:
        """Remove incomplete temporary files left by interrupted local writes."""
        managed_roots = (
            self.configuration.artifact_root,
            self.configuration.receipt_root,
            self.configuration.manifest_root,
        )
        for managed_root in managed_roots:
            for temporary in managed_root.rglob("*.tmp"):
                if temporary.is_file():
                    temporary.unlink()

    def __enter__(self) -> StateWakeWorkspace:
        """Enter the workspace context manager."""
        if self._closed:
            raise WorkspaceError("workspace is closed.")
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        """Close the workspace while preserving its filesystem state."""
        self.close()

    @staticmethod
    def _configuration_for(root: Path | str) -> WorkspaceConfiguration:
        """Resolve and validate a workspace root before filesystem mutation."""
        candidate = Path(root).expanduser()
        if candidate.exists() and not candidate.is_dir():
            raise WorkspaceError(f"workspace root is not a directory: {candidate}")
        try:
            resolved = candidate.resolve(strict=False)
        except OSError as exc:
            raise WorkspaceError("workspace root could not be resolved.") from exc
        return WorkspaceConfiguration(root=resolved)

    @staticmethod
    def _initialize_directories(configuration: WorkspaceConfiguration) -> None:
        """Create the workspace directory structure without replacing existing files."""
        for directory in configuration.required_directories():
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _create_identity(configuration: WorkspaceConfiguration) -> WorkspaceIdentity:
        """Create the stable identity written to a new workspace manifest."""
        return WorkspaceIdentity(
            workspace_id=str(uuid4()),
            created_at=datetime.now(UTC).isoformat(),
            schema_version=configuration.schema_version,
            statewake_public_api_contract_version="1",
        )

    @staticmethod
    def _write_manifest(
        configuration: WorkspaceConfiguration,
        identity: WorkspaceIdentity,
    ) -> None:
        """Persist a canonical, human-readable workspace manifest atomically."""
        payload = {
            "workspace_id": identity.workspace_id,
            "schema_version": identity.schema_version,
            "statewake_version": _statewake_version(),
            "public_api_contract_version": identity.statewake_public_api_contract_version,
            "created_at": identity.created_at,
            "storage_backend": "sqlite",
            "artifact_store": "content-addressed-sha256",
            "policy_ids": [],
            "features": [],
        }
        text = (
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=_MANIFEST_INDENT,
                sort_keys=True,
            )
            + "\n"
        )
        atomic_write_text(configuration.manifest_path, text)

    @staticmethod
    def _read_manifest(configuration: WorkspaceConfiguration) -> WorkspaceIdentity:
        """Load and validate an existing workspace manifest."""
        try:
            payload: dict[str, Any] = json.loads(
                configuration.manifest_path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkspaceManifestError(
                "workspace manifest could not be read."
            ) from exc
        # if not isinstance(payload, dict):
        #     raise WorkspaceManifestError("workspace manifest must contain a JSON object.")
        required = (
            "workspace_id",
            "created_at",
            "schema_version",
            "public_api_contract_version",
        )
        if any(not isinstance(payload.get(field), str) for field in required):
            raise WorkspaceManifestError(
                "workspace manifest has invalid identity fields."
            )
        schema_version = payload["schema_version"]
        if schema_version != _MANIFEST_SCHEMA_VERSION:
            raise WorkspaceSchemaError(
                f"unsupported workspace schema version: {schema_version}"
            )
        return WorkspaceIdentity(
            workspace_id=payload["workspace_id"],
            created_at=payload["created_at"],
            schema_version=schema_version,
            statewake_public_api_contract_version=payload[
                "public_api_contract_version"
            ],
        )


def _statewake_version() -> str:
    """Return the package version without changing the canonical package API."""
    from .. import __version__

    return __version__


__all__ = [
    "StateWakeWorkspace",
    "WorkspaceError",
    "WorkspaceManifestError",
    "WorkspaceSchemaError",
]
