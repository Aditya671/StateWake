"""Compatibility tests for the workspace backend abstraction."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from statewake.workspace import (
    SqlAlchemyWorkspaceRepository,
    SqliteWorkspaceRepository,
    StateWakeWorkspace,
    WorkspaceRecordQuery,
)


def _capture(workspace: StateWakeWorkspace) -> None:
    workspace.ingest(
        b"backend-contract",
        producer_type="test",
        producer_id="backend",
        source_ref="test://backend",
        captured_at=datetime(2026, 1, 2, tzinfo=UTC),
    )


def _query_shape(workspace: StateWakeWorkspace) -> tuple[object, ...]:
    page = workspace.query(WorkspaceRecordQuery(limit=10))
    assert page.total_count == 1
    record = page.records[0]
    return (
        record.record_id,
        record.receipt_id,
        record.artifact_digest,
        record.artifact_size,
        record.producer_id,
        record.producer_type,
        record.source_ref,
        record.run_id,
        record.captured_at,
        record.sensitivity,
        record.policy_id,
        record.verification_status,
        record.reliability_state,
        record.created_at,
    )


def test_sqlite_and_sqlalchemy_backends_share_query_contract(tmp_path: Path) -> None:
    sqlite = StateWakeWorkspace.open(tmp_path / "sqlite")
    _capture(sqlite)

    sqlalchemy = StateWakeWorkspace.open(
        tmp_path / "sqlalchemy",
        repository=SqlAlchemyWorkspaceRepository(
            tmp_path / "sqlalchemy" / "statewake.db"
        ),
    )
    _capture(sqlalchemy)

    assert _query_shape(sqlite) == _query_shape(sqlalchemy)
    sqlalchemy.repository.dispose()  # type: ignore[attr-defined]


def test_workspace_default_backend_remains_sqlite(tmp_path: Path) -> None:
    workspace = StateWakeWorkspace.open(tmp_path / "default")
    assert isinstance(workspace.repository, SqliteWorkspaceRepository)


def test_sqlalchemy_backend_classifies_missing_dependency(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    real_import: Callable[..., ModuleType] = cast(Any, __import__)

    def blocked(name: str, *args: Any, **kwargs: Any) -> ModuleType:
        if name == "sqlalchemy":
            raise ImportError("blocked for test")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", cast(Any, blocked))
    with pytest.raises(RuntimeError, match="optional 'sqlalchemy'"):
        SqlAlchemyWorkspaceRepository(tmp_path / "statewake.db")


def test_sqlalchemy_backend_supports_retention_and_integrity_contract(
    tmp_path: Path,
) -> None:
    workspace = StateWakeWorkspace.open(
        tmp_path / "sqlalchemy",
        repository=SqlAlchemyWorkspaceRepository(
            tmp_path / "sqlalchemy" / "statewake.db"
        ),
    )
    record = workspace.ingest(
        b"backend-contract",
        producer_type="test",
        producer_id="backend",
        source_ref="test://backend",
        captured_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    workspace.repository.upsert_retention(
        object_id=record.record_id,
        policy_id=record.policy_id,
        sensitivity=record.sensitivity,
        retain_until=None,
        legal_hold=True,
    )
    retention = workspace.repository.get_retention(record.record_id)
    assert retention is not None
    assert retention.legal_hold is True
    report = workspace.verify()
    assert report is not None
    assert report.status in {"healthy", "healthy_with_limitations"}
    workspace.repository.dispose()  # type: ignore[attr-defined]
