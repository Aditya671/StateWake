"""Regression tests for the durable workspace operational index."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import statewake
from statewake.workspace import (
    CorruptWorkspaceDatabaseError,
    StateWakeWorkspace,
    UnsupportedWorkspaceSchemaError,
    WorkspaceError,
)


def test_workspace_initializes_versioned_sqlite_index(tmp_path: Path) -> None:
    """Verify the workspace creates the explicit version-one operational schema."""
    workspace = StateWakeWorkspace.open(tmp_path / ".statewake")

    assert workspace.configuration.database_path.is_file()
    with sqlite3.connect(workspace.configuration.database_path) as database:
        assert database.execute("PRAGMA user_version").fetchone()[0] == 1
        tables = {
            row[0]
            for row in database.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        }
        assert tables == {
            "workspace",
            "runs",
            "records",
            "relationships",
            "state_transitions",
            "retention",
            "exports",
            "deletions",
        }
        indexes = {
            row[0]
            for row in database.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='index' AND name NOT LIKE 'sqlite_%'"
            )
        }
        assert indexes == {
            "idx_runs_producer_started",
            "idx_records_producer_captured",
            "idx_records_run_captured",
            "idx_records_artifact_digest",
            "idx_records_receipt_id",
            "idx_relationships_target",
            "idx_state_transitions_subject_occurred",
            "idx_retention_policy",
            "idx_exports_created",
            "idx_deletions_deleted_at",
        }
        row = database.execute(
            "SELECT workspace_id, schema_version, statewake_version, "
            "public_api_contract FROM workspace"
        ).fetchone()
    assert row == (
        workspace.identity.workspace_id,
        workspace.identity.schema_version,
        statewake.__version__,
        workspace.identity.statewake_public_api_contract_version,
    )


def test_sqlite_index_survives_close_and_reopen(tmp_path: Path) -> None:
    """Verify workspace metadata survives the host process lifecycle boundary."""
    root = tmp_path / ".statewake"
    first = StateWakeWorkspace.open(root)
    identity = first.identity
    first.close()

    reopened = StateWakeWorkspace.open(root)

    assert reopened.identity == identity
    assert reopened.repository.get_workspace_identity() == identity


def test_workspace_metadata_write_is_atomic(tmp_path: Path) -> None:
    """Verify failed metadata writes roll back without replacing valid metadata."""
    workspace = StateWakeWorkspace.open(tmp_path / ".statewake")
    original = workspace.identity

    replacement = type(original)(
        workspace_id="different-workspace",
        created_at=original.created_at,
        schema_version=original.schema_version,
        statewake_public_api_contract_version=original.statewake_public_api_contract_version,
    )
    with pytest.raises(CorruptWorkspaceDatabaseError):
        with workspace.repository.transaction() as transaction:
            transaction.set_workspace_metadata(replacement, "0.1.0")

    assert workspace.repository.get_workspace_identity() == original


def test_unsupported_database_schema_is_classifiable(tmp_path: Path) -> None:
    """Verify a newer database schema is rejected with a typed error."""
    root = tmp_path / ".statewake"
    workspace = StateWakeWorkspace.open(root)
    workspace.close()
    with sqlite3.connect(root / "statewake.db") as database:
        database.execute("PRAGMA user_version = 99")

    with pytest.raises(UnsupportedWorkspaceSchemaError):
        StateWakeWorkspace.open(root)


def test_corrupt_database_is_classifiable(tmp_path: Path) -> None:
    """Verify invalid SQLite bytes are exposed as a repository corruption error."""
    root = tmp_path / ".statewake"
    workspace = StateWakeWorkspace.open(root)
    workspace.close()
    (root / "statewake.db").write_bytes(b"not a sqlite database")

    with pytest.raises(CorruptWorkspaceDatabaseError):
        StateWakeWorkspace.open(root)


def test_workspace_ingest_delegates_to_existing_statewake_and_indexes_receipt(
    tmp_path: Path,
) -> None:
    """Verify workspace ingestion reuses the canonical StateWake stores and index."""
    from datetime import UTC, datetime

    root = tmp_path / ".statewake"
    workspace = StateWakeWorkspace.open(root)
    record = workspace.ingest(
        b"hello statewake",
        producer_type="test-producer",
        producer_id="producer-1",
        source_ref="source-1",
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_event_id="event-1",
        run_id=None,
    )

    assert record.record_id == record.receipt.receipt_id
    assert (
        root / "artifacts" / record.artifact_digest[:2] / record.artifact_digest[2:]
    ).is_file()
    assert (root / "receipts" / f"{record.receipt_id}.json").is_file()

    with sqlite3.connect(root / "statewake.db") as database:
        row = database.execute(
            "SELECT record_id, receipt_id, artifact_digest, artifact_size, "
            "producer_id, producer_type, source_ref, source_event_id, captured_at "
            "FROM records WHERE record_id = ?",
            (record.record_id,),
        ).fetchone()

    assert row == (
        record.record_id,
        record.receipt_id,
        record.artifact_digest,
        record.artifact_size,
        record.producer_id,
        record.producer_type,
        record.source_ref,
        record.source_event_id,
        record.captured_at.isoformat(),
    )


def test_workspace_ingest_preserves_existing_identity_conflict_semantics(
    tmp_path: Path,
) -> None:
    """Verify conflicting producer events still fail at the existing receipt boundary."""
    from datetime import UTC, datetime

    workspace = StateWakeWorkspace.open(tmp_path / ".statewake")
    captured_at = datetime(2026, 1, 1, tzinfo=UTC)
    first = workspace.ingest(
        b"first",
        producer_type="test-producer",
        producer_id="producer-1",
        source_ref="source-1",
        source_event_id="event-1",
        captured_at=captured_at,
    )

    with pytest.raises(ValueError, match="source_event_id conflict"):
        workspace.ingest(
            b"different",
            producer_type="test-producer",
            producer_id="producer-1",
            source_ref="source-1",
            source_event_id="event-1",
            captured_at=captured_at,
        )

    with sqlite3.connect(workspace.configuration.database_path) as database:
        count = database.execute("SELECT COUNT(*) FROM records").fetchone()[0]

    assert count == 1
    assert first.record_id


def test_workspace_ingest_rejects_use_after_close(tmp_path: Path) -> None:
    """Verify a closed workspace cannot be used to ingest new evidence."""
    from datetime import UTC, datetime

    workspace = StateWakeWorkspace.open(tmp_path / ".statewake")
    workspace.close()

    with pytest.raises(WorkspaceError, match="workspace is closed"):
        workspace.ingest(
            b"closed",
            producer_type="test-producer",
            producer_id="producer-1",
            source_ref="source-1",
            captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
