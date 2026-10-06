"""Errors raised by the StateWake workspace repository and integration boundary."""


class WorkspaceRepositoryError(Exception):
    """Base class for workspace repository failures."""


class UnsupportedWorkspaceSchemaError(WorkspaceRepositoryError):
    """Raised when a workspace database uses an unsupported schema."""


class CorruptWorkspaceDatabaseError(WorkspaceRepositoryError):
    """Raised when the workspace database cannot be trusted as valid state."""


class WorkspaceRecordConflictError(WorkspaceRepositoryError):
    """Raised when the workspace index conflicts with an existing receipt identity."""


class ReadOnlyWorkspaceError(WorkspaceRepositoryError):
    """Raised when a mutation is attempted through a read-only workspace handle."""


__all__ = [
    "CorruptWorkspaceDatabaseError",
    "UnsupportedWorkspaceSchemaError",
    "ReadOnlyWorkspaceError",
    "WorkspaceRecordConflictError",
    "WorkspaceRepositoryError",
]
