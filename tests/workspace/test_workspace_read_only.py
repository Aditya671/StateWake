"""Fail-safe tests for non-mutating workspace inspection access."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from statewake.workspace import StateWakeWorkspace, WorkspaceError
from statewake.workspace.errors import ReadOnlyWorkspaceError


def _snapshot(root: Path) -> dict[str, tuple[int, str | None]]:
    """Return durable file content plus bounded SQLite SHM sidecar state.

    SQLite's ``-shm`` file is transient shared-memory coordination state for WAL
    readers. Opening a database read-only may legitimately update lock/header bytes
    in that sidecar without mutating any durable workspace record. All other files
    are compared by exact content digest rather than filesystem mtimes.
    """
    snapshot: dict[str, tuple[int, str | None]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        size = path.stat().st_size
        digest = (
            None
            if relative == "statewake.db-shm"
            else sha256(path.read_bytes()).hexdigest()
        )
        snapshot[relative] = (size, digest)
    return snapshot


def test_read_only_open_does_not_create_or_modify_workspace_files(
    tmp_path: Path,
) -> None:
    """Opening and querying must not change durable workspace content."""
    root = tmp_path / ".statewake"
    writable = StateWakeWorkspace.open(root)
    record = writable.ingest(
        b"read-only-fixture",
        producer_type="test",
        producer_id="producer-1",
        source_ref="fixture",
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    writable.close()
    before = _snapshot(root)

    reader = StateWakeWorkspace.open_read_only(root)
    assert reader.read_only is True
    assert reader.get_record(record.record_id) is not None
    assert reader.repository.get_workspace_identity() == reader.identity
    assert reader.verify() is not None
    reader.close()

    assert _snapshot(root) == before


def test_read_only_handle_rejects_mutation_and_repository_transactions(
    tmp_path: Path,
) -> None:
    """Every mutation path must fail before touching durable state."""
    root = tmp_path / ".statewake"
    writable = StateWakeWorkspace.open(root)
    writable.close()
    reader = StateWakeWorkspace.open_read_only(root)

    with pytest.raises(WorkspaceError, match="read-only"):
        reader.operation_lock()
    with pytest.raises(WorkspaceError, match="read-only"):
        reader.ingest(
            b"forbidden",
            producer_type="test",
            producer_id="producer-1",
            source_ref="forbidden",
            captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    with pytest.raises(ReadOnlyWorkspaceError, match="read-only"):
        reader.repository.transaction()


def test_read_only_open_requires_existing_initialized_workspace(tmp_path: Path) -> None:
    """Inspection must never turn a missing path into a new workspace."""
    root = tmp_path / "missing"
    with pytest.raises(WorkspaceError, match="does not exist"):
        StateWakeWorkspace.open_read_only(root)
    assert not root.exists()


def test_read_only_open_rejects_foreign_key_corruption(tmp_path: Path) -> None:
    """Read-only qualification must detect referential corruption explicitly."""
    import sqlite3

    from statewake.workspace.errors import CorruptWorkspaceDatabaseError

    root = tmp_path / ".statewake"
    writable = StateWakeWorkspace.open(root)
    database_path = writable.configuration.database_path
    writable.close()

    database = sqlite3.connect(database_path)
    database.execute("PRAGMA foreign_keys=OFF")
    database.execute(
        "INSERT INTO records "
        "(record_id, producer_id, producer_type, run_id, captured_at, sensitivity, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "corrupt-record",
            "producer-1",
            "fixture",
            "missing-run",
            "2026-01-01T00:00:00+00:00",
            "internal",
            "2026-01-01T00:00:00+00:00",
        ),
    )
    database.commit()
    database.close()

    with pytest.raises(CorruptWorkspaceDatabaseError, match="foreign-key check failed"):
        StateWakeWorkspace.open_read_only(root)


def test_read_only_open_reads_existing_wal_without_mutating_durable_content(
    tmp_path: Path,
) -> None:
    """Read committed WAL state without changing durable workspace content."""
    import sqlite3

    root = tmp_path / ".statewake"
    writable = StateWakeWorkspace.open(root)
    record = writable.ingest(
        b"active-wal-fixture",
        producer_type="test",
        producer_id="producer-1",
        source_ref="fixture",
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    writable.close()

    database = sqlite3.connect(root / "statewake.db")
    try:
        database.execute("PRAGMA journal_mode=WAL")
        database.execute("PRAGMA wal_autocheckpoint=0")
        database.execute(
            "UPDATE records SET verification_status = ? WHERE record_id = ?",
            ("verified", record.record_id),
        )
        database.commit()
        assert (root / "statewake.db-wal").exists()
        assert (root / "statewake.db-shm").exists()
        before = _snapshot(root)

        reader = StateWakeWorkspace.open_read_only(root)
        observed = reader.get_record(record.record_id)
        assert observed is not None
        assert observed.verification_status == "verified"
        reader.close()

        assert _snapshot(root) == before
    finally:
        database.close()
