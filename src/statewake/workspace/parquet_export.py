"""Narrow PyArrow adapter for canonical StateWake Parquet exports."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .errors import WorkspaceRepositoryError
from .projections import DatasetProjection

PARQUET_FORMAT = "parquet"
PARQUET_METADATA_KEY = b"statewake.dataset.schema_version"
RECORD_COLUMNS = (
    "record_id",
    "receipt_id",
    "artifact_digest",
    "artifact_size",
    "producer_id",
    "producer_type",
    "producer_version",
    "source_ref",
    "source_event_id",
    "run_id",
    "captured_at",
    "sensitivity",
    "policy_id",
    "verification_status",
    "reliability_state",
    "created_at",
)


class ParquetExportError(WorkspaceRepositoryError):
    """Raised when a Parquet export cannot be created or verified."""


@dataclass(frozen=True, slots=True)
class ParquetExportResult:
    """Describe one successfully written Parquet export."""

    export_id: str
    output_path: Path
    output_digest: str
    row_count: int
    schema_version: str
    disclosure_max_sensitivity: str
    partitioned: bool


def write_parquet(
    projection: DatasetProjection,
    output: Path,
    *,
    schema_version: str,
    disclosure_max_sensitivity: str,
    query_definition: Mapping[str, object],
    partition_by: Sequence[str] = (),
) -> ParquetExportResult:
    """Write one dataset projection through the narrow PyArrow adapter."""
    pyarrow = _load_pyarrow()
    output = Path(output).expanduser()
    _validate_partition_columns(partition_by)
    rows = [record.to_dict() for record in projection.records]
    table = pyarrow.Table.from_pylist(rows, schema=_record_schema(pyarrow))
    metadata = dict(table.schema.metadata or {})
    metadata[PARQUET_METADATA_KEY] = schema_version.encode("utf-8")
    metadata[b"statewake.format"] = PARQUET_FORMAT.encode("utf-8")
    metadata[b"statewake.query"] = json.dumps(
        dict(query_definition),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    metadata[b"statewake.disclosure_max_sensitivity"] = (
        disclosure_max_sensitivity.encode("utf-8")
    )
    table = table.replace_schema_metadata(metadata)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        if partition_by:
            if output.exists() and not output.is_dir():
                raise ParquetExportError(
                    "partitioned Parquet output requires a directory path."
                )
            output.mkdir(parents=True, exist_ok=True)
            pyarrow.dataset.write_dataset(
                table,
                base_dir=output,
                format="parquet",
                partitioning=list(partition_by),
                existing_data_behavior="delete_matching",
            )
        else:
            if output.exists() and output.is_dir():
                raise ParquetExportError("file Parquet output requires a file path.")
            pyarrow.parquet.write_table(
                table,
                output,
                compression="zstd",
                use_dictionary=True,
                write_statistics=True,
            )
    except ParquetExportError:
        raise
    except (OSError, pyarrow.ArrowException) as exc:
        raise ParquetExportError(f"Parquet export could not be written: {exc}") from exc
    return ParquetExportResult(
        export_id=str(uuid4()),
        output_path=output,
        output_digest=_sha256_path(output),
        row_count=len(rows),
        schema_version=schema_version,
        disclosure_max_sensitivity=disclosure_max_sensitivity,
        partitioned=bool(partition_by),
    )


def verify_parquet(
    path: Path, *, expected_rows: int, expected_schema_version: str
) -> None:
    """Reopen one Parquet export and validate its core analytical contract."""
    pyarrow = _load_pyarrow()
    try:
        table = (
            pyarrow.dataset.dataset(path, format="parquet").to_table()
            if path.is_dir()
            else pyarrow.parquet.read_table(path)
        )
    except (OSError, pyarrow.ArrowException) as exc:
        raise ParquetExportError(
            f"Parquet export could not be reopened: {exc}"
        ) from exc
    if table.num_rows != expected_rows:
        raise ParquetExportError(
            f"Parquet row count mismatch: expected {expected_rows}, got {table.num_rows}."
        )
    if tuple(table.column_names) != RECORD_COLUMNS:
        raise ParquetExportError(
            f"Parquet schema mismatch: expected {RECORD_COLUMNS!r}, got {tuple(table.column_names)!r}."
        )
    actual = (
        (table.schema.metadata or {}).get(PARQUET_METADATA_KEY, b"").decode("utf-8")
    )
    if actual != expected_schema_version:
        raise ParquetExportError(
            f"Parquet schema metadata mismatch: expected {expected_schema_version!r}, got {actual!r}."
        )


def _load_pyarrow() -> Any:
    """Import PyArrow lazily so SQLite-only use remains lightweight."""
    try:
        import pyarrow
        import pyarrow.dataset
        import pyarrow.parquet
    except ImportError as exc:
        raise ParquetExportError(
            "Parquet export requires the declared PyArrow dependency."
        ) from exc
    return pyarrow


def _record_schema(pyarrow: Any) -> Any:
    """Build the stable Arrow schema for normalized records."""
    return pyarrow.schema(
        [
            pyarrow.field("record_id", pyarrow.string(), nullable=False),
            pyarrow.field("receipt_id", pyarrow.string(), nullable=False),
            pyarrow.field("artifact_digest", pyarrow.string(), nullable=False),
            pyarrow.field("artifact_size", pyarrow.int64(), nullable=False),
            pyarrow.field("producer_id", pyarrow.string(), nullable=False),
            pyarrow.field("producer_type", pyarrow.string(), nullable=False),
            pyarrow.field("producer_version", pyarrow.string()),
            pyarrow.field("source_ref", pyarrow.string(), nullable=False),
            pyarrow.field("source_event_id", pyarrow.string()),
            pyarrow.field("run_id", pyarrow.string()),
            pyarrow.field("captured_at", pyarrow.string(), nullable=False),
            pyarrow.field("sensitivity", pyarrow.string(), nullable=False),
            pyarrow.field("policy_id", pyarrow.string(), nullable=False),
            pyarrow.field("verification_status", pyarrow.string()),
            pyarrow.field("reliability_state", pyarrow.string()),
            pyarrow.field("created_at", pyarrow.string(), nullable=False),
        ]
    )


def _validate_partition_columns(partition_by: Sequence[str]) -> None:
    """Validate requested partition fields against the stable record schema."""
    if len(set(partition_by)) != len(partition_by):
        raise ValueError("partition_by must not contain duplicates")
    unknown = set(partition_by) - set(RECORD_COLUMNS)
    if unknown:
        raise ValueError(f"unsupported Parquet partition columns: {sorted(unknown)!r}")


def _sha256_path(path: Path) -> str:
    """Return deterministic SHA-256 identity for one output file or dataset."""
    digest = hashlib.sha256()
    if path.is_file():
        _update_digest(digest, Path(path.name), path)
        return digest.hexdigest()
    for file_path in sorted(item for item in path.rglob("*") if item.is_file()):
        _update_digest(digest, file_path.relative_to(path), file_path)
    return digest.hexdigest()


def _update_digest(digest: Any, relative_path: Path, file_path: Path) -> None:
    """Add one output path and its bytes to a digest."""
    digest.update(relative_path.as_posix().encode("utf-8"))
    digest.update(b"\0")
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)


__all__ = [
    "PARQUET_FORMAT",
    "ParquetExportError",
    "ParquetExportResult",
    "RECORD_COLUMNS",
    "verify_parquet",
    "write_parquet",
]
