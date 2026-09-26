"""Operational controls and diagnostics for a StateWake workspace."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from filelock import FileLock, Timeout

from .models import WorkspaceExport
from .repository import StateWakeRepository
from .verification import WorkspaceVerificationReport


class WorkspaceOperationLock:
    """Serialize workspace mutations through one filesystem lock."""

    def __init__(self, path: Path, *, timeout: float = 30.0) -> None:
        """Initialize a process-safe lock with a bounded acquisition timeout."""
        if timeout < 0:
            raise ValueError("timeout must be non-negative")
        self._lock = FileLock(str(path))
        self._timeout = timeout

    def __enter__(self) -> WorkspaceOperationLock:
        """Acquire the workspace mutation lock."""
        try:
            self._lock.acquire(timeout=self._timeout)
        except Timeout as exc:
            raise TimeoutError(
                "workspace operation lock could not be acquired"
            ) from exc
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        """Release the workspace mutation lock."""
        self._lock.release()


@dataclass(frozen=True, slots=True)
class WorkspaceStorageReport:
    """Report durable storage usage by workspace-owned storage category."""

    total_bytes: int
    artifact_bytes: int
    receipt_bytes: int
    database_bytes: int
    export_bytes: int
    manifest_bytes: int
    lock_bytes: int


@dataclass(frozen=True, slots=True)
class WorkspaceDiagnostics:
    """Summarize operational workspace health and durable state."""

    verification: WorkspaceVerificationReport
    storage: WorkspaceStorageReport
    export_count: int
    latest_export: WorkspaceExport | None
    backend: str


class WorkspaceDiagnosticsCollector:
    """Collect bounded, read-only workspace operational diagnostics."""

    def __init__(self, root: Path, repository: StateWakeRepository) -> None:
        """Initialize diagnostics for one workspace root and repository."""
        self._root = root
        self._repository = repository

    def collect(
        self,
        verification: WorkspaceVerificationReport,
    ) -> WorkspaceDiagnostics:
        """Return health, storage, export, and backend information."""
        exports = self._repository.list_exports(limit=1000)
        latest = exports[0] if exports else None
        return WorkspaceDiagnostics(
            verification=verification,
            storage=self.storage(),
            export_count=len(exports),
            latest_export=latest,
            backend=type(self._repository).__name__,
        )

    def storage(self) -> WorkspaceStorageReport:
        """Calculate regular-file byte usage without following symlinks."""
        categories = {
            "artifact": self._root / "artifacts",
            "receipt": self._root / "receipts",
            "export": self._root / "exports",
            "manifest": self._root / "manifests",
            "lock": self._root / "locks",
        }
        sizes = {name: _regular_file_bytes(path) for name, path in categories.items()}
        sizes["database"] = sum(
            _regular_file_bytes(self._root / suffix)
            for suffix in (
                "statewake.sqlite3",
                "statewake.sqlite3-wal",
                "statewake.sqlite3-shm",
            )
        )
        return WorkspaceStorageReport(
            total_bytes=sum(sizes.values()),
            artifact_bytes=sizes["artifact"],
            receipt_bytes=sizes["receipt"],
            database_bytes=sizes["database"],
            export_bytes=sizes["export"],
            manifest_bytes=sizes["manifest"],
            lock_bytes=sizes["lock"],
        )


def _regular_file_bytes(path: Path) -> int:
    """Sum regular-file bytes beneath a path without following symlinks."""
    if not path.exists() and not path.is_symlink():
        return 0
    if path.is_symlink():
        return 0
    if path.is_file():
        try:
            mode = path.stat(follow_symlinks=False).st_mode
            return path.stat(follow_symlinks=False).st_size if stat.S_ISREG(mode) else 0
        except OSError:
            return 0
    total = 0
    try:
        with os.scandir(path) as iterator:
            for entry in iterator:
                child = Path(entry.path)
                if entry.is_symlink():
                    continue
                if entry.is_file(follow_symlinks=False):
                    try:
                        total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
                elif entry.is_dir(follow_symlinks=False):
                    total += _regular_file_bytes(child)
    except OSError:
        return total
    return total


__all__ = [
    "WorkspaceDiagnostics",
    "WorkspaceDiagnosticsCollector",
    "WorkspaceOperationLock",
    "WorkspaceStorageReport",
]
