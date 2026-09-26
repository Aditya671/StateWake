"""Regression tests for Phase 4 workspace durability guarantees."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from statewake.workspace import (
    StateWakeWorkspace,
    WorkspaceError,
    WorkspaceIntegritySweepError,
    WorkspaceRecordQuery,
    WorkspaceRestoreError,
)
from statewake.workspace.migrations import MIGRATION_IDS


def test_default_workspace_opens_data_statewake_sqlite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default workspace creation must be durable and not fall back to temp storage."""
    monkeypatch.chdir(tmp_path)

    workspace = StateWakeWorkspace.open()

    assert workspace.root == tmp_path / "data" / "statewake"
    assert workspace.configuration.database_path == workspace.root / "statewake.db"
    assert workspace.configuration.database_path.is_file()


def test_workspace_schema_version_is_recorded(tmp_path: Path) -> None:
    """The manifest, workspace metadata, and SQLite user_version expose schema identity."""
    workspace = StateWakeWorkspace.open(tmp_path / "statewake")

    manifest = json.loads(
        workspace.configuration.manifest_path.read_text(encoding="utf-8")
    )
    with sqlite3.connect(workspace.configuration.database_path) as database:
        user_version = database.execute("PRAGMA user_version").fetchone()[0]
        stored = database.execute("SELECT schema_version FROM workspace").fetchone()[0]

    assert manifest["schema_version"] == "1"
    assert stored == "1"
    assert user_version == 1


def test_migration_registry_records_phase_compatibility_markers() -> None:
    """Versioned migration modules are explicit even when no physical DDL is required."""
    assert MIGRATION_IDS == (
        "v0001_initial",
        "v0002_ai_contracts",
        "v0003_claim_profile_results",
    )


def test_migration_from_v1_preserves_receipts_and_states(tmp_path: Path) -> None:
    """Reopening a schema-v1 workspace preserves indexed records and state fields."""
    root = tmp_path / "statewake"
    workspace = StateWakeWorkspace.open(root)
    record = workspace.ingest(
        b"payload",
        producer_type="phase4-test",
        producer_id="tester",
        source_ref="unit-test",
        captured_at=datetime(2026, 9, 21, tzinfo=UTC),
    )
    workspace.close()

    reopened = StateWakeWorkspace.open(root)
    page = reopened.query(WorkspaceRecordQuery(limit=10))

    assert [item.record_id for item in page.records] == [record.record_id]
    assert page.records[0].verification_status is None
    assert page.records[0].reliability_state is None


def test_backup_restore_round_trip_preserves_candidate_fingerprint(
    tmp_path: Path,
) -> None:
    """Backup and restore must preserve workspace identity and record fingerprint."""
    workspace = StateWakeWorkspace.open(tmp_path / "source")
    record = workspace.ingest(
        b"candidate-fingerprint-payload",
        producer_type="phase4-test",
        producer_id="tester",
        source_ref="fingerprint",
        captured_at=datetime(2026, 9, 21, tzinfo=UTC),
    )

    backup = workspace.backup(tmp_path / "backup.zip")
    restored = StateWakeWorkspace.restore_backup(
        backup.output_path, tmp_path / "restored"
    )
    restored_workspace = StateWakeWorkspace.open(restored.workspace_root)
    restored_record = restored_workspace.get_record(record.record_id)

    assert restored.workspace_id == workspace.identity.workspace_id
    assert restored_record is not None
    assert restored_record.artifact_digest == record.artifact_digest
    assert restored_record.receipt.to_dict() == record.receipt.to_dict()


def test_restore_rejects_modified_payload_digest(tmp_path: Path) -> None:
    """Restored payloads remain content-address verified after extraction."""
    workspace = StateWakeWorkspace.open(tmp_path / "source")
    workspace.ingest(
        b"payload-to-tamper",
        producer_type="phase4-test",
        producer_id="tester",
        source_ref="tamper",
        captured_at=datetime(2026, 9, 21, tzinfo=UTC),
    )
    backup = workspace.backup(tmp_path / "backup.zip")
    restored = StateWakeWorkspace.restore_backup(
        backup.output_path, tmp_path / "restored"
    )
    artifact = next((restored.workspace_root / "artifacts").rglob("*"))
    while not artifact.is_file():
        artifact = next(artifact.rglob("*"))
    artifact.write_bytes(b"tampered")

    with pytest.raises(WorkspaceIntegritySweepError):
        StateWakeWorkspace.open(restored.workspace_root).integrity_sweep()


def test_backup_restore_rejects_tampered_backup_member(tmp_path: Path) -> None:
    """Restore must reject a backup whose member no longer matches its checksum."""
    workspace = StateWakeWorkspace.open(tmp_path / "source")
    workspace.ingest(
        b"payload",
        producer_type="phase4-test",
        producer_id="tester",
        source_ref="tamper-backup",
        captured_at=datetime(2026, 9, 21, tzinfo=UTC),
    )
    backup = workspace.backup(tmp_path / "backup.zip")
    tampered = tmp_path / "tampered.zip"
    with (
        ZipFile(backup.output_path) as source,
        ZipFile(tampered, "w", ZIP_DEFLATED) as target,
    ):
        for name in source.namelist():
            data = source.read(name)
            if name.endswith("manifest.json") and name != "backup-manifest.json":
                data = b"{}\n"
            target.writestr(name, data)

    with pytest.raises(WorkspaceRestoreError, match="checksum mismatch"):
        StateWakeWorkspace.restore_backup(tampered, tmp_path / "restored")


def test_export_import_preserves_profile_report_links(tmp_path: Path) -> None:
    """Backup restore preserves Phase 2/3 payload evidence link records."""
    workspace = StateWakeWorkspace.open(tmp_path / "source")
    profile_record = workspace.ingest(
        b'{"profile_id":"rag_answer_verified.v1","decision":"accepted"}',
        producer_type="claim-profile-result",
        producer_id="statewake-phase2",
        source_ref="profile-result.json",
        captured_at=datetime(2026, 9, 21, tzinfo=UTC),
    )
    report_record = workspace.ingest(
        b"# Verification Report\nprofile_evaluation_digest: linked\n",
        producer_type="verification-report",
        producer_id="statewake-phase3",
        source_ref="report.md",
        captured_at=datetime(2026, 9, 21, tzinfo=UTC),
    )

    backup = workspace.backup(tmp_path / "backup.zip")
    restored = StateWakeWorkspace.restore_backup(
        backup.output_path, tmp_path / "restored"
    )
    restored_workspace = StateWakeWorkspace.open(restored.workspace_root)

    assert restored_workspace.get_record(profile_record.record_id) is not None
    assert restored_workspace.get_record(report_record.record_id) is not None


def test_backup_rejects_unverified_workspace(tmp_path: Path) -> None:
    """Backup refuses to preserve a workspace with broken referenced evidence."""
    workspace = StateWakeWorkspace.open(tmp_path / "source")
    record = workspace.ingest(
        b"payload",
        producer_type="phase4-test",
        producer_id="tester",
        source_ref="missing",
        captured_at=datetime(2026, 9, 21, tzinfo=UTC),
    )
    for path in (workspace.root / "artifacts").rglob("*"):
        if path.is_file() and record.artifact_digest[2:] in path.name:
            path.unlink()
            break

    with pytest.raises(WorkspaceError):
        workspace.backup(tmp_path / "backup.zip")


def test_backup_records_consistent_single_read_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Archive checksum must bind the same bytes actually written into the ZIP."""
    workspace = StateWakeWorkspace.open(tmp_path / "source")
    workspace.ingest(
        b"immutable-artifact",
        producer_type="test",
        producer_id="tester",
        source_ref="one-read",
        captured_at=datetime(2026, 9, 23, tzinfo=UTC),
    )
    original = Path.read_bytes
    artifact_reads: dict[str, int] = {}

    def counting_read(path: Path) -> bytes:
        if "artifacts" in path.parts:
            name = str(path)
            artifact_reads[name] = artifact_reads.get(name, 0) + 1
            if artifact_reads[name] > 1:
                return b"changed-between-checksum-and-archive"
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", counting_read)
    from statewake.workspace.backup import create_workspace_backup

    backup = create_workspace_backup(
        workspace.root,
        tmp_path / "backup.zip",
        workspace_id=workspace.identity.workspace_id,
        schema_version=workspace.identity.schema_version,
    )
    # Restrict the instrumented read count to backup creation, not restore.
    assert max(artifact_reads.values()) == 1
    monkeypatch.undo()
    restored = StateWakeWorkspace.restore_backup(
        backup.output_path, tmp_path / "restored"
    )
    assert restored.restored_files == backup.file_count


def test_backup_includes_committed_wal_state_without_sidecar(
    tmp_path: Path,
) -> None:
    """SQLite backup API must include committed WAL data in one DB image."""
    workspace = StateWakeWorkspace.open(tmp_path / "source")
    record = workspace.ingest(
        b"wal-payload",
        producer_type="test",
        producer_id="tester",
        source_ref="wal-state",
        captured_at=datetime(2026, 9, 23, tzinfo=UTC),
    )
    with sqlite3.connect(workspace.configuration.database_path) as database:
        database.execute("PRAGMA wal_autocheckpoint=0")
        database.execute(
            "UPDATE records SET verification_status = ? WHERE record_id = ?",
            ("verified", record.record_id),
        )
        database.commit()
        backup = workspace.backup(tmp_path / "backup.zip")
        with ZipFile(backup.output_path) as archive:
            assert "statewake.db" in archive.namelist()
            assert not any(
                name.endswith(("-wal", "-shm")) for name in archive.namelist()
            )
        restored = StateWakeWorkspace.restore_backup(
            backup.output_path, tmp_path / "restored"
        )
    with sqlite3.connect(restored.workspace_root / "statewake.db") as db:
        assert (
            db.execute(
                "SELECT verification_status FROM records WHERE record_id = ?",
                (record.record_id,),
            ).fetchone()[0]
            == "verified"
        )
    assert StateWakeWorkspace.open(restored.workspace_root).get_record(record.record_id)
