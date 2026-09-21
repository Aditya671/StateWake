"""Optional read-only analytical access to exported StateWake datasets."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import WorkspaceRepositoryError

DUCKDB_FORMAT = "duckdb"
_DATASET_MARKER = "__STATEWAKE_PARQUET__"
_READONLY_SQL_PATTERN = re.compile(
    r"\b(?:INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|COPY|ATTACH|DETACH|EXPORT|"
    r"IMPORT|PRAGMA|CALL|VACUUM|SET|INSTALL|LOAD|TRUNCATE|MERGE)\b",
    re.IGNORECASE,
)


class AnalyticalAccessError(WorkspaceRepositoryError):
    """Raised when optional analytical access cannot be performed safely."""


@dataclass(slots=True)
class AnalyticalQueryResult:
    """Describe a lazily fetched analytical query over a Parquet relation."""

    columns: tuple[str, ...]
    _cursor: Any

    def fetchmany(self, size: int = 1024) -> tuple[tuple[Any, ...], ...]:
        """Fetch one bounded batch without materializing the full result."""
        if size < 1:
            raise ValueError("size must be positive.")
        return tuple(self._cursor.fetchmany(size))

    def close(self) -> None:
        """Close the underlying analytical cursor and connection."""
        self._cursor.close()


class DuckDBAnalyticalAdapter:
    """Provide read-only analytical access without owning StateWake records."""

    def query_parquet(
        self,
        parquet_path: Path,
        sql: str,
        *,
        parameters: Sequence[object] = (),
    ) -> AnalyticalQueryResult:
        """Execute one read-only query against a Parquet source."""
        path = Path(parquet_path).expanduser().resolve(strict=True)
        wrapped_sql = _inject_parquet_source(sql)
        return _query_with_bound_path(path, wrapped_sql, parameters)

    def snapshot_parquet(
        self,
        parquet_path: Path,
        output: Path,
        sql: str,
        *,
        parameters: Sequence[object] = (),
    ) -> Path:
        """Persist an explicit analytical query result to a separate Parquet file."""
        duckdb = _load_duckdb()
        path = Path(parquet_path).expanduser().resolve(strict=True)
        wrapped_sql = _inject_parquet_source(sql)
        destination = Path(output).expanduser().resolve(strict=False)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise AnalyticalAccessError("analytical snapshot output already exists.")
        _validate_read_only_query(sql)
        connection = duckdb.connect(database=":memory:")
        temporary = destination.with_name(f".{destination.name}.tmp")
        try:
            connection.execute(
                f"COPY ({wrapped_sql}) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
                (str(path), *tuple(parameters), str(temporary)),
            )
            temporary.replace(destination)
            return destination
        except Exception as exc:
            if temporary.exists():
                temporary.unlink()
            raise AnalyticalAccessError(f"analytical snapshot failed: {exc}") from exc
        finally:
            connection.close()


def query_parquet(
    parquet_path: Path,
    sql: str,
    *,
    parameters: Sequence[object] = (),
) -> AnalyticalQueryResult:
    """Execute one read-only query against a Parquet source."""
    return DuckDBAnalyticalAdapter().query_parquet(
        parquet_path,
        sql,
        parameters=parameters,
    )


def query_exported_parquet(
    parquet_path: Path,
    sql: str,
    *,
    parameters: Sequence[object] = (),
) -> AnalyticalQueryResult:
    """Compatibility alias for querying one exported Parquet dataset."""
    return query_parquet(parquet_path, sql, parameters=parameters)


def snapshot_parquet(
    parquet_path: Path,
    output: Path,
    sql: str,
    *,
    parameters: Sequence[object] = (),
) -> Path:
    """Persist an explicit analytical query result to a separate Parquet file."""
    return DuckDBAnalyticalAdapter().snapshot_parquet(
        parquet_path,
        output,
        sql,
        parameters=parameters,
    )


def _inject_parquet_source(sql: str) -> str:
    """Replace the explicit StateWake dataset marker with a bound Parquet relation."""
    _validate_read_only_query(sql)
    if sql.count(_DATASET_MARKER) != 1:
        raise ValueError(
            "analytical SQL must contain exactly one __STATEWAKE_PARQUET__ marker."
        )
    return sql.replace(_DATASET_MARKER, "read_parquet(?)", 1)


def _validate_read_only_query(sql: str) -> None:
    """Reject non-read-only or multi-statement analytical SQL."""
    statement = sql.strip()
    if not statement:
        raise ValueError("analytical SQL must not be blank.")
    upper = statement.upper()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        raise ValueError(
            "analytical queries must be read-only SELECT or WITH statements."
        )
    if ";" in statement.rstrip(";"):
        raise ValueError("analytical queries must contain one statement.")
    if _READONLY_SQL_PATTERN.search(statement):
        raise ValueError("analytical SQL contains a prohibited mutating command.")


def _load_duckdb() -> Any:
    """Load the optional DuckDB dependency without affecting core persistence."""
    try:
        import duckdb
    except ImportError as exc:
        raise AnalyticalAccessError(
            "DuckDB analytical access requires the optional duckdb dependency."
        ) from exc
    return duckdb


def _query_with_bound_path(
    path: Path,
    sql: str,
    parameters: Sequence[object],
) -> AnalyticalQueryResult:
    """Execute a read-only analytical query with a bound Parquet path."""
    duckdb = _load_duckdb()
    connection = duckdb.connect(database=":memory:")
    try:
        cursor = connection.execute(sql, (str(path), *tuple(parameters)))
        columns = tuple(item[0] for item in cursor.description or ())
        return AnalyticalQueryResult(columns, _CursorOwner(cursor, connection))
    except Exception as exc:
        connection.close()
        raise AnalyticalAccessError(f"analytical query failed: {exc}") from exc


class _CursorOwner:
    """Keep the in-memory DuckDB connection alive with one analytical cursor."""

    def __init__(self, cursor: Any, connection: Any) -> None:
        """Initialize one cursor and its owning connection."""
        self._cursor = cursor
        self._connection = connection

    @property
    def description(self) -> Any:
        """Expose the cursor description used to construct query columns."""
        return self._cursor.description

    def fetchmany(self, size: int) -> Any:
        """Fetch one bounded batch from the underlying cursor."""
        return self._cursor.fetchmany(size)

    def close(self) -> None:
        """Close both the analytical cursor and its owning connection."""
        self._cursor.close()
        self._connection.close()


__all__ = [
    "AnalyticalAccessError",
    "AnalyticalQueryResult",
    "DuckDBAnalyticalAdapter",
    "DUCKDB_FORMAT",
    "query_exported_parquet",
    "query_parquet",
    "snapshot_parquet",
]
