"""Public workspace foundation for durable StateWake state."""

from .analytical import (
    AnalyticalAccessError,
    AnalyticalQueryResult,
    DuckDBAnalyticalAdapter,
)
from .backup import WorkspaceBackupError, WorkspaceBackupResult, create_workspace_backup
from .configuration import WorkspaceConfiguration
from .csv_export import CsvExportError, CsvExportResult
from .errors import (
    CorruptWorkspaceDatabaseError,
    UnsupportedWorkspaceSchemaError,
    WorkspaceRepositoryError,
)
from .integration import WorkspaceIngestionAdapter
from .integrity_sweep import (
    WorkspaceIntegritySweepError,
    WorkspaceIntegritySweepResult,
    sweep_workspace_payload_integrity,
)
from .json_export import JSON_FORMAT, JsonExportError, JsonExportResult
from .lifecycle import WorkspaceLifecycle, WorkspaceLifecycleResult
from .models import (
    WorkspaceExport,
    WorkspaceIdentity,
    WorkspaceQueryPage,
    WorkspaceRecord,
    WorkspaceRecordIndexEntry,
    WorkspaceRecordQuery,
    WorkspaceRetention,
)
from .operations import (
    WorkspaceDiagnostics,
    WorkspaceDiagnosticsCollector,
    WorkspaceOperationLock,
    WorkspaceStorageReport,
)
from .parquet_export import ParquetExportError, ParquetExportResult
from .portable_bundle import (
    BUNDLE_FORMAT,
    PortableBundleError,
    PortableBundleResult,
)
from .projections import (
    DATASET_PROJECTION_SCHEMA_VERSION,
    DatasetProjection,
    DeletionProjection,
    NormalizedRecordProjection,
    RelationshipProjection,
    RetentionProjection,
    RunProjection,
    StateTransitionProjection,
)
from .restore import (
    WorkspaceRestoreError,
    WorkspaceRestoreResult,
    restore_workspace_backup,
)
from .sqlalchemy_repository import SqlAlchemyWorkspaceRepository
from .sqlite_repository import SqliteWorkspaceRepository
from .verification import (
    WorkspaceVerificationIssue,
    WorkspaceVerificationReport,
    WorkspaceVerificationStatus,
    WorkspaceVerifier,
)
from .workspace import (
    StateWakeWorkspace,
    WorkspaceError,
    WorkspaceManifestError,
    WorkspaceSchemaError,
)
from .xlsx_export import XlsxExportError, XlsxExportResult

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
