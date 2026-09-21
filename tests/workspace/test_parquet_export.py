from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from statewake.workspace.models import WorkspaceRecordQuery
from statewake.workspace.parquet_export import (
    ParquetExportError,
    ParquetExportResult,
    _validate_partition_columns,
)


def test_missing_pyarrow_is_classified() -> None:
    import statewake.workspace.parquet_export as module

    original = module.__dict__.pop("pyarrow", None)
    try:
        with pytest.raises(ParquetExportError, match="PyArrow"):
            module._load_pyarrow()
    finally:
        if original is not None:
            module.__dict__["pyarrow"] = original


def test_partition_columns_are_bounded() -> None:
    _validate_partition_columns(("producer_id", "sensitivity"))

    with pytest.raises(ValueError, match="duplicates"):
        _validate_partition_columns(("producer_id", "producer_id"))

    with pytest.raises(ValueError, match="unsupported"):
        _validate_partition_columns(("not_a_column",))


def test_export_result_carries_identity_and_shape(tmp_path: Path) -> None:
    result = ParquetExportResult(
        export_id="export-1",
        output_path=tmp_path / "dataset.parquet",
        output_digest="a" * 64,
        row_count=2,
        schema_version="1",
        disclosure_max_sensitivity="internal",
        partitioned=False,
    )
    assert result.row_count == 2
    assert result.output_digest == "a" * 64
    assert result.schema_version == "1"


def test_query_definition_values_are_compatible_with_export_filters() -> None:
    query = WorkspaceRecordQuery(
        producer_id="producer",
        max_sensitivity="internal",
        captured_from=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert query.max_sensitivity == "internal"
    assert query.captured_from is not None


def test_export_orchestration_records_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from statewake.workspace.integration import WorkspaceIngestionAdapter
    from statewake.workspace.sqlite_repository import SqliteWorkspaceRepository

    repository = SqliteWorkspaceRepository(tmp_path / "statewake.db")
    repository.initialize()
    adapter = WorkspaceIngestionAdapter(tmp_path, repository)
    monkeypatch.setattr(
        cast(Any, adapter), "project", lambda _query: SimpleNamespace(records=())
    )

    result = ParquetExportResult(
        export_id="export-1",
        output_path=tmp_path / "dataset.parquet",
        output_digest="b" * 64,
        row_count=0,
        schema_version="1",
        disclosure_max_sensitivity="internal",
        partitioned=False,
    )
    monkeypatch.setattr(
        "statewake.workspace.integration.write_parquet", lambda *a, **k: result
    )
    monkeypatch.setattr(
        "statewake.workspace.integration.verify_parquet", lambda *a, **k: None
    )

    query = WorkspaceRecordQuery(limit=10)
    observed = adapter.export_parquet(
        query, result.output_path, max_sensitivity="internal"
    )
    assert observed == result

    import sqlite3

    with sqlite3.connect(tmp_path / "statewake.db") as database:
        row = database.execute(
            "SELECT format, disclosure_max_sensitivity, row_count FROM exports WHERE export_id = ?",
            ("export-1",),
        ).fetchone()
    assert row == ("parquet", "internal", 0)


def test_export_metadata_identity_conflict_is_classified(tmp_path: Path) -> None:
    from statewake.workspace.errors import WorkspaceRecordConflictError
    from statewake.workspace.sqlite_repository import SqliteWorkspaceRepository

    repository = SqliteWorkspaceRepository(tmp_path / "statewake.db")
    repository.initialize()
    repository.record_export(
        export_id="export-1",
        created_at=datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        query_definition_json="{}",
        disclosure_max_sensitivity="internal",
        source_schema_version="1",
        output_path="dataset.parquet",
        output_digest="a" * 64,
        row_count=0,
    )
    with pytest.raises(WorkspaceRecordConflictError, match="export identity conflict"):
        repository.record_export(
            export_id="export-1",
            created_at=datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
            query_definition_json="{}",
            disclosure_max_sensitivity="internal",
            source_schema_version="1",
            output_path="dataset.parquet",
            output_digest="a" * 64,
            row_count=0,
        )
