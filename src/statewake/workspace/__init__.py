"""Public workspace foundation for durable StateWake state."""

from statewake.workspace.analytical import (
    AnalyticalAccessError,
    AnalyticalQueryResult,
    DuckDBAnalyticalAdapter,
)
from statewake.workspace.backup import (
    WorkspaceBackupError,
    WorkspaceBackupResult,
    create_workspace_backup,
)
from statewake.workspace.configuration import WorkspaceConfiguration
from statewake.workspace.csv_export import CsvExportError, CsvExportResult
from statewake.workspace.errors import (
    CorruptWorkspaceDatabaseError,
    UnsupportedWorkspaceSchemaError,
    WorkspaceRepositoryError,
)
from statewake.workspace.integration import WorkspaceIngestionAdapter
from statewake.workspace.integrity_sweep import (
    WorkspaceIntegritySweepError,
    WorkspaceIntegritySweepResult,
    sweep_workspace_payload_integrity,
)
from statewake.workspace.json_export import (
    JSON_FORMAT,
    JsonExportError,
    JsonExportResult,
)
from statewake.workspace.lifecycle import WorkspaceLifecycle, WorkspaceLifecycleResult
from statewake.workspace.models import (
    WorkspaceExport,
    WorkspaceIdentity,
    WorkspaceQueryPage,
    WorkspaceRecord,
    WorkspaceRecordIndexEntry,
    WorkspaceRecordQuery,
    WorkspaceRetention,
)
from statewake.workspace.operations import (
    WorkspaceDiagnostics,
    WorkspaceDiagnosticsCollector,
    WorkspaceOperationLock,
    WorkspaceStorageReport,
)
from statewake.workspace.parquet_export import ParquetExportError, ParquetExportResult
from statewake.workspace.portable_bundle import (
    BUNDLE_FORMAT,
    PortableBundleError,
    PortableBundleResult,
)
from statewake.workspace.projections import (
    DATASET_PROJECTION_SCHEMA_VERSION,
    DatasetProjection,
    DeletionProjection,
    NormalizedRecordProjection,
    RelationshipProjection,
    RetentionProjection,
    RunProjection,
    StateTransitionProjection,
)
from statewake.workspace.restore import (
    WorkspaceRestoreError,
    WorkspaceRestoreResult,
    restore_workspace_backup,
)
from statewake.workspace.sqlalchemy_repository import SqlAlchemyWorkspaceRepository
from statewake.workspace.sqlite_repository import SqliteWorkspaceRepository
from statewake.workspace.verification import (
    WorkspaceVerificationIssue,
    WorkspaceVerificationReport,
    WorkspaceVerificationStatus,
    WorkspaceVerifier,
)
from statewake.workspace.workspace import (
    StateWakeWorkspace,
    WorkspaceError,
    WorkspaceManifestError,
    WorkspaceSchemaError,
)
from statewake.workspace.xlsx_export import XlsxExportError, XlsxExportResult

__all__ = [
    "StateWakeWorkspace",
    "AnalyticalAccessError",
    "AnalyticalQueryResult",
    "DuckDBAnalyticalAdapter",
    "WorkspaceBackupError",
    "WorkspaceBackupResult",
    "create_workspace_backup",
    "WorkspaceConfiguration",
    "WorkspaceError",
    "CsvExportError",
    "CsvExportResult",
    "WorkspaceIdentity",
    "WorkspaceQueryPage",
    "WorkspaceRecord",
    "WorkspaceRecordIndexEntry",
    "WorkspaceRecordQuery",
    "WorkspaceIntegritySweepError",
    "WorkspaceIntegritySweepResult",
    "sweep_workspace_payload_integrity",
    "WorkspaceIngestionAdapter",
    "WorkspaceRepositoryError",
    "UnsupportedWorkspaceSchemaError",
    "CorruptWorkspaceDatabaseError",
    "SqliteWorkspaceRepository",
    "SqlAlchemyWorkspaceRepository",
    "WorkspaceManifestError",
    "WorkspaceSchemaError",
    "DATASET_PROJECTION_SCHEMA_VERSION",
    "DatasetProjection",
    "DeletionProjection",
    "NormalizedRecordProjection",
    "RelationshipProjection",
    "RetentionProjection",
    "RunProjection",
    "StateTransitionProjection",
    "ParquetExportError",
    "ParquetExportResult",
    "XlsxExportError",
    "XlsxExportResult",
    "JSON_FORMAT",
    "JsonExportError",
    "JsonExportResult",
    "BUNDLE_FORMAT",
    "PortableBundleError",
    "PortableBundleResult",
    "WorkspaceRestoreError",
    "WorkspaceRestoreResult",
    "restore_workspace_backup",
    "WorkspaceDiagnostics",
    "WorkspaceDiagnosticsCollector",
    "WorkspaceOperationLock",
    "WorkspaceStorageReport",
    "WorkspaceLifecycle",
    "WorkspaceLifecycleResult",
    "WorkspaceRetention",
    "WorkspaceVerificationIssue",
    "WorkspaceVerificationReport",
    "WorkspaceVerificationStatus",
    "WorkspaceVerifier",
    "WorkspaceExport",
]
