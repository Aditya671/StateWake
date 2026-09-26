"""Multiple observations of one run retain producer authority and time bounds."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from statewake.workspace import StateWakeWorkspace
from statewake.workspace.errors import WorkspaceRecordConflictError
from statewake.workspace.sqlite_repository import SqliteWorkspaceRepository

BASE = datetime(2026, 9, 21, tzinfo=UTC)


def _write(
    workspace: StateWakeWorkspace, name: str, offset: int, *, producer: str = "producer"
):
    return workspace.ingest(
        name.encode(),
        producer_type="test",
        producer_id=producer,
        source_ref=f"event:{name}",
        source_event_id=name,
        captured_at=BASE + timedelta(seconds=offset),
        run_id="shared-run",
    )


def test_distinct_events_same_run_different_times_and_out_of_order(
    tmp_path: Path,
) -> None:
    workspace = StateWakeWorkspace.open(tmp_path / "workspace")
    try:
        later = _write(workspace, "later", 20)
        earlier = _write(workspace, "earlier", 10)
        latest = _write(workspace, "latest", 30)
        for record in (later, earlier, latest):
            workspace.verify(record)
        repository = workspace.repository
        assert isinstance(repository, SqliteWorkspaceRepository)
        with repository.connect() as database:
            run = database.execute(
                "SELECT producer_id, started_at, finished_at FROM runs WHERE run_id = ?",
                ("shared-run",),
            ).fetchone()
            assert run == (
                "producer",
                (BASE + timedelta(seconds=10)).isoformat(),
                (BASE + timedelta(seconds=30)).isoformat(),
            )
            assert (
                database.execute(
                    "SELECT COUNT(*) FROM records WHERE run_id = ?",
                    ("shared-run",),
                ).fetchone()[0]
                == 3
            )
    finally:
        workspace.close()


def test_same_run_rejects_different_producer_without_altering_index(
    tmp_path: Path,
) -> None:
    workspace = StateWakeWorkspace.open(tmp_path / "workspace")
    try:
        original = _write(workspace, "first", 10)
        with pytest.raises(WorkspaceRecordConflictError, match="run identity conflict"):
            _write(workspace, "wrong-producer", 20, producer="other")
        workspace.verify(original)
        repository = workspace.repository
        assert isinstance(repository, SqliteWorkspaceRepository)
        with repository.connect() as database:
            assert database.execute(
                "SELECT producer_id, started_at, finished_at FROM runs WHERE run_id = ?",
                ("shared-run",),
            ).fetchone() == (
                "producer",
                (BASE + timedelta(seconds=10)).isoformat(),
                (BASE + timedelta(seconds=10)).isoformat(),
            )
            assert database.execute("SELECT COUNT(*) FROM records").fetchone()[0] == 1
    finally:
        workspace.close()
