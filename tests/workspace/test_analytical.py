"""Regression tests for optional DuckDB analytical access."""

from pathlib import Path
from unittest.mock import patch

import pytest

import statewake.workspace.analytical as analytical


class FakeCursor:
    """Minimal cursor contract used to verify bounded analytical fetching."""

    description = [("record_id",), ("artifact_size",)]

    def __init__(self) -> None:
        self.fetch_sizes: list[int] = []
        self.closed = False

    def fetchmany(self, size: int) -> list[tuple[object, ...]]:
        self.fetch_sizes.append(size)
        return [("r1", 3)]

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    """Minimal read-only analytical connection used by adapter tests."""

    def __init__(self) -> None:
        self.cursor = FakeCursor()
        self.statements: list[tuple[str, tuple[object, ...]]] = []
        self.closed = False

    def execute(self, sql: str, parameters: tuple[object, ...]) -> FakeCursor:
        self.statements.append((sql, parameters))
        if sql.startswith("COPY ("):
            assert isinstance(parameters[-1], str)
            Path(parameters[-1]).write_bytes(b"snapshot")
        return self.cursor

    def close(self) -> None:
        self.closed = True


class FakeDuckDB:
    """Minimal DuckDB module contract required by the adapter."""

    def __init__(self) -> None:
        self.connection = FakeConnection()

    def connect(self, *, database: str) -> FakeConnection:
        assert database == ":memory:"
        return self.connection


def test_query_is_bounded_and_binds_parquet_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Query execution must stream batches rather than materialize all rows."""
    source = tmp_path / "records.parquet"
    source.write_bytes(b"not parsed by fake")
    fake = FakeDuckDB()
    monkeypatch.setattr(analytical, "_load_duckdb", lambda: fake)

    result = analytical.query_parquet(
        source,
        "SELECT record_id, artifact_size FROM __STATEWAKE_PARQUET__ WHERE artifact_size > ?",
        parameters=(2,),
    )

    assert result.columns == ("record_id", "artifact_size")
    assert result.fetchmany(1) == (("r1", 3),)
    assert fake.connection.cursor.fetch_sizes == [1]
    sql, parameters = fake.connection.statements[0]
    assert "read_parquet(?)" in sql
    assert parameters == (str(source.resolve()), 2)
    result.close()
    assert fake.connection.closed is True
    assert fake.connection.cursor.closed is True


def test_query_rejects_mutation_and_multi_statement_sql(tmp_path: Path) -> None:
    """Analytical access must reject SQL that can mutate state."""
    source = tmp_path / "records.parquet"
    source.write_bytes(b"x")
    adapter = analytical.DuckDBAnalyticalAdapter()

    with pytest.raises(ValueError, match="read-only"):
        adapter.query_parquet(
            source,
            "DELETE FROM __STATEWAKE_PARQUET__ WHERE record_id = 'r1'",
        )
    with pytest.raises(ValueError, match="one statement"):
        adapter.query_parquet(
            source,
            "SELECT * FROM __STATEWAKE_PARQUET__; SELECT 1",
        )


def test_query_requires_exactly_one_dataset_marker(tmp_path: Path) -> None:
    """Queries cannot inject unrelated filesystem sources."""
    source = tmp_path / "records.parquet"
    source.write_bytes(b"x")
    adapter = analytical.DuckDBAnalyticalAdapter()

    with pytest.raises(ValueError, match="exactly one"):
        adapter.query_parquet(source, "SELECT 1")

    with pytest.raises(ValueError, match="exactly one"):
        adapter.query_parquet(
            source,
            "SELECT * FROM __STATEWAKE_PARQUET__ UNION ALL "
            "SELECT * FROM __STATEWAKE_PARQUET__",
        )


def test_snapshot_has_explicit_separate_output_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Snapshots must write a distinct output rather than mutate source data."""
    source = tmp_path / "records.parquet"
    source.write_bytes(b"source")
    output = tmp_path / "snapshot.parquet"
    fake = FakeDuckDB()
    monkeypatch.setattr(analytical, "_load_duckdb", lambda: fake)

    result = analytical.snapshot_parquet(
        source,
        output,
        "SELECT record_id FROM __STATEWAKE_PARQUET__ WHERE sensitivity = ?",
        parameters=("internal",),
    )

    assert result == output.resolve()
    assert output.read_bytes() == b"snapshot"
    assert source.read_bytes() == b"source"
    sql, parameters = fake.connection.statements[0]
    assert sql.startswith("COPY (SELECT")
    assert parameters[0] == str(source.resolve())
    assert isinstance(parameters[-1], str)
    assert parameters[-1].endswith(".snapshot.parquet.tmp")
    assert parameters[1] == "internal"
    assert fake.connection.closed is True


def test_missing_optional_dependency_is_classified(tmp_path: Path) -> None:
    """Core workspace use must remain possible when DuckDB is absent."""
    source = tmp_path / "records.parquet"
    source.write_bytes(b"x")

    with patch.dict("sys.modules", {"duckdb": None}):
        with pytest.raises(analytical.AnalyticalAccessError, match="optional duckdb"):
            analytical.query_parquet(source, "SELECT * FROM __STATEWAKE_PARQUET__")


def test_workspace_exposes_analytical_boundary_without_repository_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Workspace analytical access must not require or mutate authoritative records."""
    fake = FakeDuckDB()
    monkeypatch.setattr(analytical, "_load_duckdb", lambda: fake)

    from statewake.workspace import StateWakeWorkspace

    with StateWakeWorkspace.open(tmp_path / "workspace") as workspace:
        source = tmp_path / "records.parquet"
        source.write_bytes(b"source")
        result = workspace.query_parquet(
            source,
            "SELECT record_id FROM __STATEWAKE_PARQUET__",
        )
        assert result.fetchmany(100) == (("r1", 3),)
        result.close()

        snapshot = workspace.snapshot_parquet(
            source,
            tmp_path / "snapshot.parquet",
            "SELECT record_id FROM __STATEWAKE_PARQUET__",
        )
        assert snapshot.exists()
