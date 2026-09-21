"""Deterministic CSV adapter for StateWake dataset projections."""

from __future__ import annotations

import csv
import hashlib
import os
import tempfile
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .errors import WorkspaceRepositoryError
from .projections import NormalizedRecordProjection

CSV_FORMAT = "csv"
CSV_NULL = r"\N"
CSV_ENCODING = "utf-8"
CSV_LINE_TERMINATOR = "\n"
CSV_RECORD_COLUMNS = (
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


class CsvExportError(WorkspaceRepositoryError):
    """Raised when a CSV export cannot be created or validated."""


@dataclass(frozen=True, slots=True)
class CsvExportResult:
    """Describe one successfully written CSV export."""

    export_id: str
    output_path: Path
    output_digest: str
    row_count: int
    schema_version: str
    disclosure_max_sensitivity: str


def write_csv(
    records: Iterable[NormalizedRecordProjection],
    output: Path,
    *,
    schema_version: str,
    disclosure_max_sensitivity: str,
    query_definition: Mapping[str, object],
) -> CsvExportResult:
    """Stream normalized records to a deterministic UTF-8 CSV file."""
    output = Path(output).expanduser()
    if output.exists() and output.is_dir():
        raise CsvExportError("CSV output requires a file path.")
    output.parent.mkdir(parents=True, exist_ok=True)

    row_count = 0
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=CSV_ENCODING,
            newline="",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            writer = csv.writer(
                handle,
                delimiter=",",
                quotechar='"',
                lineterminator=CSV_LINE_TERMINATOR,
                quoting=csv.QUOTE_MINIMAL,
            )
            writer.writerow(CSV_RECORD_COLUMNS)
            for record in records:
                writer.writerow(_record_row(record))
                row_count += 1
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, output)
        temporary_path = None
    except CsvExportError:
        raise
    except (OSError, csv.Error) as exc:
        raise CsvExportError(f"CSV export could not be written: {exc}") from exc
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except OSError:
                pass

    return CsvExportResult(
        export_id=str(uuid4()),
        output_path=output,
        output_digest=_sha256_file(output),
        row_count=row_count,
        schema_version=schema_version,
        disclosure_max_sensitivity=disclosure_max_sensitivity,
    )


def verify_csv(
    path: Path,
    *,
    expected_rows: int,
    expected_schema_version: str,
) -> None:
    """Reopen CSV and validate its stable header, row count, and null contract."""
    path = Path(path)
    if not path.is_file():
        raise CsvExportError(f"CSV export does not exist: {path}")
    try:
        with path.open("r", encoding=CSV_ENCODING, newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if tuple(header or ()) != CSV_RECORD_COLUMNS:
                raise CsvExportError(
                    f"CSV schema mismatch: expected {CSV_RECORD_COLUMNS!r}, "
                    f"got {tuple(header or ())!r}."
                )
            row_count = 0
            for row in reader:
                if len(row) != len(CSV_RECORD_COLUMNS):
                    raise CsvExportError(
                        "CSV row width mismatch: "
                        f"expected {len(CSV_RECORD_COLUMNS)}, got {len(row)}."
                    )
                if any(value == "" for value in row):
                    raise CsvExportError("CSV contains an unencoded null value.")
                row_count += 1
    except CsvExportError:
        raise
    except (OSError, UnicodeError, csv.Error) as exc:
        raise CsvExportError(f"CSV export could not be reopened: {exc}") from exc
    if row_count != expected_rows:
        raise CsvExportError(
            f"CSV row count mismatch: expected {expected_rows}, got {row_count}."
        )
    if expected_schema_version.strip() == "":
        raise CsvExportError("CSV schema version must not be blank.")


def _record_row(record: NormalizedRecordProjection) -> tuple[str, ...]:
    """Convert one normalized record to the stable CSV representation."""
    values = record.to_dict()
    return tuple(_csv_value(values[column]) for column in CSV_RECORD_COLUMNS)


def _csv_value(value: object) -> str:
    """Encode one value using explicit CSV null and deterministic text semantics."""
    if value is None:
        return CSV_NULL
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 identity of one CSV output file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "CSV_ENCODING",
    "CSV_FORMAT",
    "CSV_LINE_TERMINATOR",
    "CSV_NULL",
    "CSV_RECORD_COLUMNS",
    "CsvExportError",
    "CsvExportResult",
    "verify_csv",
    "write_csv",
]
