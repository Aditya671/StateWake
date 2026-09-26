from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from statewake.domain.data_lifecycle import DataLifecyclePolicy
from statewake.workspace import StateWakeWorkspace, WorkspaceRecordQuery

BASE = datetime(2026, 1, 1, 12, tzinfo=UTC)


def _workspace_record(workspace: StateWakeWorkspace):
    return workspace.ingest(
        b"payload",
        producer_type="test",
        producer_id="producer",
        source_ref="source",
        captured_at=BASE,
    )


def test_retention_is_durable_and_legal_hold_blocks_expiration(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    with StateWakeWorkspace.open(root) as workspace:
        record = _workspace_record(workspace)
        policy = DataLifecyclePolicy(
            policy_id="retain-1", purpose="test", max_retention_days=1
        )
        retention = workspace.apply_retention(
            record.record_id, policy, legal_hold=True, now=BASE
        )
        assert retention.legal_hold
        assert workspace.repository.get_retention(record.record_id) == retention
        decision = workspace.evaluate_lifecycle(
            record.record_id, policy, now=BASE + timedelta(days=2)
        )
        assert decision.expired
        assert not decision.deletion_allowed

    with StateWakeWorkspace.open(root) as reopened:
        stored_retention = reopened.repository.get_retention(record.record_id)
        assert stored_retention is not None
        assert stored_retention.legal_hold


def test_expired_record_deletion_uses_existing_artifact_store_and_keeps_tombstone(
    tmp_path: Path,
) -> None:
    with StateWakeWorkspace.open(tmp_path / "workspace") as workspace:
        record = _workspace_record(workspace)
        policy = DataLifecyclePolicy(
            policy_id="retain-1", purpose="test", max_retention_days=1
        )
        workspace.apply_retention(record.record_id, policy, now=BASE)
        result = workspace.delete_expired(
            record.record_id, now=BASE + timedelta(days=2)
        )
        assert result.action == "delete"
        assert result.deletion is not None
        assert not (
            workspace.configuration.artifact_root
            / record.artifact_digest[:2]
            / record.artifact_digest[2:]
        ).exists()

        with pytest.raises(FileNotFoundError):
            workspace.verify(record)

        deletion = workspace.repository.get_deletion(record.record_id)
        assert deletion is not None
        assert deletion.object_id == record.record_id
        assert deletion.digest == record.artifact_digest
        assert not hasattr(deletion, "content")


def test_unexpired_record_cannot_be_deleted(tmp_path: Path) -> None:
    with StateWakeWorkspace.open(tmp_path / "workspace") as workspace:
        record = _workspace_record(workspace)
        policy = DataLifecyclePolicy(
            policy_id="retain-1", purpose="test", max_retention_days=10
        )
        workspace.apply_retention(record.record_id, policy, now=BASE)
        with pytest.raises(PermissionError, match="blocked by lifecycle policy"):
            workspace.delete_expired(record.record_id, now=BASE + timedelta(days=1))


def test_no_maximum_retention_never_expires(tmp_path: Path) -> None:
    with StateWakeWorkspace.open(tmp_path / "workspace") as workspace:
        record = _workspace_record(workspace)
        policy = DataLifecyclePolicy(policy_id="forever", purpose="test")
        workspace.apply_retention(record.record_id, policy, now=BASE)
        decision = workspace.evaluate_lifecycle(
            record.record_id, policy, now=BASE + timedelta(days=3650)
        )
        assert not decision.expired
        with pytest.raises(PermissionError):
            workspace.delete_expired(record.record_id, now=BASE + timedelta(days=3650))


def test_export_retention_is_independently_managed_and_path_bounded(
    tmp_path: Path,
) -> None:
    with StateWakeWorkspace.open(tmp_path / "workspace") as workspace:
        record = _workspace_record(workspace)
        export = workspace.export_json(
            WorkspaceRecordQuery(record_id=record.record_id),
            workspace.configuration.export_root / "json" / "sample.json",
        )
        policy = DataLifecyclePolicy(
            policy_id="export-retain", purpose="export", max_retention_days=1
        )
        stored_export = workspace.repository.get_export(export.export_id)
        assert stored_export is not None
        export_created = datetime.fromisoformat(stored_export.created_at)
        retention = workspace.apply_export_retention(
            export.export_id, policy, now=export_created
        )
        assert retention.object_id == f"export:{export.export_id}"
        result = workspace.delete_expired_export(
            export.export_id, now=export_created + timedelta(days=2)
        )
        assert result.action == "delete-export"
        assert not export.output_path.exists()
        assert workspace.repository.get_deletion(retention.object_id) is not None


def test_export_retention_rejects_path_outside_workspace(tmp_path: Path) -> None:
    with StateWakeWorkspace.open(tmp_path / "workspace") as workspace:
        record = _workspace_record(workspace)
        export = workspace.export_json(
            WorkspaceRecordQuery(record_id=record.record_id), tmp_path / "outside.json"
        )
        policy = DataLifecyclePolicy(
            policy_id="export-retain", purpose="export", max_retention_days=1
        )
        stored_export = workspace.repository.get_export(export.export_id)
        assert stored_export is not None
        export_created = datetime.fromisoformat(stored_export.created_at)
        workspace.apply_export_retention(export.export_id, policy, now=export_created)
        with pytest.raises(PermissionError, match="outside the workspace export root"):
            workspace.delete_expired_export(
                export.export_id, now=export_created + timedelta(days=2)
            )


def test_expiry_state_and_tombstone_survive_restart(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    with StateWakeWorkspace.open(root) as workspace:
        record = _workspace_record(workspace)
        policy = DataLifecyclePolicy(
            policy_id="retain-1", purpose="test", max_retention_days=1
        )
        workspace.apply_retention(record.record_id, policy, now=BASE)

    with StateWakeWorkspace.open(root) as reopened:
        decision = reopened.evaluate_lifecycle(
            record.record_id, policy, now=BASE + timedelta(days=2)
        )
        assert decision.expired
        result = reopened.delete_expired(record.record_id, now=BASE + timedelta(days=2))
        assert result.deletion is not None
        assert reopened.repository.get_deletion(record.record_id) is not None
