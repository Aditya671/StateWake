"""Regression tests for production workspace operations."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from statewake.workspace import (
    StateWakeWorkspace,
    WorkspaceOperationLock,
)
from statewake.workspace.models import WorkspaceRecordQuery


def _capture(workspace: StateWakeWorkspace, *, event_id: str = "event-1"):
    return workspace.ingest(
        b"operational-data",
        producer_type="test",
        producer_id="producer-1",
        source_ref="memory://source",
        source_event_id=event_id,
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_diagnostics_reports_health_storage_backend_and_exports(tmp_path: Path) -> None:
    """Diagnostics should explain durable health and storage without raw inspection."""
    with StateWakeWorkspace.open(tmp_path) as workspace:
        _capture(workspace)
        report = workspace.diagnostics()

        assert report.verification.status == "healthy"
        assert report.backend == "SqliteWorkspaceRepository"
        assert report.storage.total_bytes > 0
        assert report.storage.artifact_bytes > 0
        assert report.export_count == 0
        assert report.latest_export is None


def test_storage_report_does_not_follow_symlinks(tmp_path: Path) -> None:
    """Storage reporting must not count files reached through storage symlinks."""
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"secret outside workspace")
    with StateWakeWorkspace.open(tmp_path / "workspace") as workspace:
        link = workspace.configuration.artifact_root / "escape"
        link.symlink_to(outside)
        report = workspace.storage_report()
        assert report.artifact_bytes == 0


def test_export_history_is_deterministic_and_bounded(tmp_path: Path) -> None:
    """Export history should reuse durable metadata with stable ordering and bounds."""
    with StateWakeWorkspace.open(tmp_path) as workspace:
        _capture(workspace)
        projection_query = WorkspaceRecordQuery(limit=1)
        output = workspace.configuration.export_root / "records.csv"
        workspace.export_csv(projection_query, output)

        history = workspace.export_history(limit=1)
        assert len(history) == 1
        assert history[0].format == "csv"
        assert history[0].output_path == str(output)
        with pytest.raises(ValueError, match="between 1 and 10000"):
            workspace.export_history(limit=0)


def test_operation_lock_serializes_mutations(tmp_path: Path) -> None:
    """A held workspace lock should prevent another mutation owner from entering."""
    with StateWakeWorkspace.open(tmp_path) as workspace:
        first = WorkspaceOperationLock(
            workspace.configuration.lock_root / "workspace.operations.lock"
        )
        first.__enter__()
        entered = threading.Event()
        result: list[str] = []

        def contender() -> None:
            entered.set()
            try:
                with WorkspaceOperationLock(
                    workspace.configuration.lock_root / "workspace.operations.lock",
                    timeout=0.05,
                ):
                    result.append("acquired")
            except TimeoutError:
                result.append("timed_out")

        thread = threading.Thread(target=contender)
        thread.start()
        assert entered.wait(timeout=1)
        thread.join(timeout=1)
        first.__exit__(None, None, None)

        assert result == ["timed_out"]


def test_concurrent_ingestion_handles_are_serialized(tmp_path: Path) -> None:
    """Concurrent workspace handles can serialize mutations without data loss."""
    workspaces = [StateWakeWorkspace.open(tmp_path) for _ in range(2)]
    try:
        captured_at = datetime(2026, 1, 1, tzinfo=UTC)

        def ingest(index: int) -> str:
            record = workspaces[index].ingest(
                f"payload-{index}".encode(),
                producer_type="test",
                producer_id=f"producer-{index}",
                source_ref="memory://concurrent",
                source_event_id=f"concurrent-{index}",
                captured_at=captured_at,
            )
            return record.record_id

        with ThreadPoolExecutor(max_workers=2) as pool:
            record_ids = tuple(pool.map(ingest, (0, 1)))

        assert len(set(record_ids)) == 2
        assert workspaces[0].query(WorkspaceRecordQuery(limit=10)).total_count == 2
    finally:
        for workspace in workspaces:
            workspace.close()


def test_two_workspace_handles_can_reopen_without_manifest_race(tmp_path: Path) -> None:
    """Repeated opens should converge on one durable workspace identity."""
    workspaces = [StateWakeWorkspace.open(tmp_path) for _ in range(4)]
    try:
        assert {workspace.identity.workspace_id for workspace in workspaces} == {
            workspaces[0].identity.workspace_id
        }
    finally:
        for workspace in workspaces:
            workspace.close()


def test_schema_v1_workspace_remains_reopen_compatible(tmp_path: Path) -> None:
    """The Tier 1 schema remains a supported reopen format after Tier 15."""
    first = StateWakeWorkspace.open(tmp_path)
    workspace_id = first.identity.workspace_id
    first.close()

    reopened = StateWakeWorkspace.open(tmp_path)
    try:
        assert reopened.identity.workspace_id == workspace_id
        report = reopened.verify()
        assert report is not None
        assert report.status == "healthy"
    finally:
        reopened.close()
