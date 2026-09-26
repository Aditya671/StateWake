"""Regression tests for StateWake workspace restart and recovery guarantees."""

from __future__ import annotations

import errno
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from statewake.workspace import StateWakeWorkspace
from statewake.workspace.errors import CorruptWorkspaceDatabaseError


def _ingest(workspace: StateWakeWorkspace, content: bytes = b"durable evidence") -> str:
    """Write one deterministic evidence record and return its record identity."""
    record = workspace.ingest(
        content,
        producer_type="test-producer",
        producer_id="producer-1",
        source_ref="source-1",
        source_event_id="event-1",
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    return record.record_id


def _read_record_ids(database_path: Path) -> list[str]:
    """Read indexed record identities for recovery verification."""
    with sqlite3.connect(database_path) as database:
        return [
            str(row[0])
            for row in database.execute(
                "SELECT record_id FROM records ORDER BY record_id"
            ).fetchall()
        ]


def test_committed_record_survives_close_reopen(tmp_path: Path) -> None:
    """Verify committed StateWake records remain after the application closes."""
    root = tmp_path / ".statewake"
    workspace = StateWakeWorkspace.open(root)
    record_id = _ingest(workspace)
    workspace.close()

    reopened = StateWakeWorkspace.open(root)

    assert _read_record_ids(reopened.configuration.database_path) == [record_id]
    reopened.verify(reopened_record(reopened, record_id))


def reopened_record(workspace: StateWakeWorkspace, record_id: str):
    """Load a persisted record through the canonical receipt store for verification."""
    from statewake.adapters.evidence_ingestion import JsonEvidenceReceiptStore
    from statewake.workspace.models import WorkspaceRecord

    receipt_store = JsonEvidenceReceiptStore(workspace.root / "receipts")
    receipt = receipt_store.get(record_id)
    return WorkspaceRecord(
        record_id=record_id, receipt=receipt, created_at=receipt.captured_at
    )


def test_duplicate_write_is_idempotent_across_restart(tmp_path: Path) -> None:
    """Verify retrying the same write does not duplicate its committed index row."""
    root = tmp_path / ".statewake"
    first = StateWakeWorkspace.open(root)
    first_id = _ingest(first)
    first.close()

    reopened = StateWakeWorkspace.open(root)
    retry_id = _ingest(reopened)

    assert retry_id == first_id
    assert _read_record_ids(root / "statewake.db") == [first_id]


def test_filesystem_permission_failure_does_not_index_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a simulated permission failure leaves the operational index unchanged."""
    workspace = StateWakeWorkspace.open(tmp_path / ".statewake")
    ingestion = workspace._ingestion._ingestion

    def deny_write(content: bytes) -> str:
        """Simulate the underlying artifact filesystem denying a write."""
        del content
        raise PermissionError(errno.EACCES, "permission denied")

    monkeypatch.setattr(ingestion.artifact_store, "put", deny_write)

    with pytest.raises(PermissionError, match="permission denied"):
        _ingest(workspace)

    assert _read_record_ids(workspace.configuration.database_path) == []


def test_disk_full_simulation_does_not_index_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify a simulated ENOSPC failure leaves the operational index unchanged."""
    workspace = StateWakeWorkspace.open(tmp_path / ".statewake")
    ingestion = workspace._ingestion._ingestion

    def disk_full(content: bytes) -> str:
        """Simulate the underlying artifact filesystem exhausting available space."""
        del content
        raise OSError(errno.ENOSPC, "no space left on device")

    monkeypatch.setattr(ingestion.artifact_store, "put", disk_full)

    with pytest.raises(OSError, match="no space left on device"):
        _ingest(workspace)

    assert _read_record_ids(workspace.configuration.database_path) == []


def test_retry_after_interrupted_index_write_recovers_from_existing_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify an interrupted index step can be retried without replacing canonical evidence."""
    root = tmp_path / ".statewake"
    workspace = StateWakeWorkspace.open(root)

    original_index = workspace.repository.index_record
    state = {"failed": False}

    def fail_once(record):
        """Interrupt the first operational-index write after evidence capture."""
        if not state["failed"]:
            state["failed"] = True
            raise OSError("simulated interrupted index write")
        original_index(record)

    monkeypatch.setattr(workspace.repository, "index_record", fail_once)

    with pytest.raises(OSError, match="simulated interrupted index write"):
        _ingest(workspace)

    with sqlite3.connect(root / "statewake.db") as database:
        assert database.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 0
    assert len(list((root / "artifacts").rglob("*"))) > 0
    assert len(list((root / "receipts").glob("*.json"))) == 1

    retried = workspace.ingest(
        b"durable evidence",
        producer_type="test-producer",
        producer_id="producer-1",
        source_ref="source-1",
        source_event_id="event-1",
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert _read_record_ids(root / "statewake.db") == [retried.record_id]


def test_recovery_removes_stale_temporary_files(tmp_path: Path) -> None:
    """Verify startup recovery removes incomplete local-write remnants."""
    root = tmp_path / ".statewake"
    workspace = StateWakeWorkspace.open(root)
    stale_artifact = workspace.configuration.artifact_root / "orphan.tmp"
    stale_receipt = workspace.configuration.receipt_root / "orphan.json.tmp"
    stale_manifest = workspace.configuration.manifest_root / "orphan.json.tmp"
    stale_artifact.write_bytes(b"partial")
    stale_receipt.write_text("partial", encoding="utf-8")
    stale_manifest.write_text("partial", encoding="utf-8")
    workspace.close()

    reopened = StateWakeWorkspace.open(root)

    assert not stale_artifact.exists()
    assert not stale_receipt.exists()
    assert not stale_manifest.exists()
    assert reopened.repository.get_workspace_identity() == reopened.identity


def test_missing_artifact_is_detected_after_restart(tmp_path: Path) -> None:
    """Verify canonical verification detects a missing payload after restart."""
    root = tmp_path / ".statewake"
    workspace = StateWakeWorkspace.open(root)
    record = workspace.ingest(
        b"payload",
        producer_type="test-producer",
        producer_id="producer-1",
        source_ref="source-1",
        source_event_id="event-1",
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    workspace.close()

    artifact = (
        workspace.configuration.artifact_root
        / record.artifact_digest[:2]
        / record.artifact_digest[2:]
    )
    artifact.unlink()
    reopened = StateWakeWorkspace.open(root)

    with pytest.raises(FileNotFoundError, match="Artifact not found"):
        reopened.verify(record)


def test_corrupt_database_is_rejected_during_recovery(tmp_path: Path) -> None:
    """Verify restart recovery never silently recreates an invalid database."""
    root = tmp_path / ".statewake"
    workspace = StateWakeWorkspace.open(root)
    workspace.close()
    database_path = root / "statewake.db"
    database_path.write_bytes(b"not sqlite")

    with pytest.raises(CorruptWorkspaceDatabaseError):
        StateWakeWorkspace.open(root)
