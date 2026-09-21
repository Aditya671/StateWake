"""Deterministic JSON dataset export for StateWake workspaces."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .projections import DatasetProjection

JSON_FORMAT = "json"
JSON_ENCODING = "utf-8"
JSON_SCHEMA_VERSION = "1"


class JsonExportError(ValueError):
    """Raised when a workspace JSON export is invalid or cannot be verified."""


@dataclass(frozen=True, slots=True)
class JsonExportResult:
    """Describe one completed deterministic JSON dataset export."""

    export_id: str
    output_path: Path
    output_digest: str
    row_count: int
    schema_version: str
    disclosure_max_sensitivity: str


def write_json(
    projection: DatasetProjection,
    output: Path,
    *,
    schema_version: str,
    disclosure_max_sensitivity: str,
    query_definition: dict[str, object],
) -> JsonExportResult:
    """Write a canonical, independently parseable JSON dataset document."""
    payload = {
        "format": JSON_FORMAT,
        "schema_version": schema_version,
        "disclosure_max_sensitivity": disclosure_max_sensitivity,
        "query": query_definition,
        "dataset": projection.to_dict(),
    }
    content = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode(JSON_ENCODING)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(f".{output.name}.tmp")
    try:
        with temp.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, output)
    except OSError as exc:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
        raise JsonExportError(f"unable to write JSON export: {exc}") from exc

    digest = sha256(content).hexdigest()
    export_id = digest
    return JsonExportResult(
        export_id=export_id,
        output_path=output,
        output_digest=digest,
        row_count=len(projection.records),
        schema_version=schema_version,
        disclosure_max_sensitivity=disclosure_max_sensitivity,
    )


def verify_json(
    path: Path,
    *,
    expected_rows: int,
    expected_schema_version: str,
) -> None:
    """Verify canonical JSON structure, schema, row count, and safe encoding."""
    if not path.is_file():
        raise JsonExportError(f"JSON export does not exist: {path}")
    raw = path.read_bytes()
    try:
        payload: dict[str, Any] | None = json.loads(raw.decode(JSON_ENCODING))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise JsonExportError("JSON export is not valid UTF-8 JSON.") from exc
    if not isinstance(payload, dict):
        raise JsonExportError("JSON export root must be an object.")
    if payload.get("format") != JSON_FORMAT:
        raise JsonExportError("JSON export format marker is invalid.")
    if payload.get("schema_version") != expected_schema_version:
        raise JsonExportError("JSON export schema version is invalid.")
    if payload.get("disclosure_max_sensitivity") in (None, ""):
        raise JsonExportError("JSON export disclosure ceiling is missing.")
    query = payload.get("query")
    dataset = payload.get("dataset")
    if not isinstance(query, dict) or not isinstance(dataset, dict):
        raise JsonExportError("JSON export query and dataset must be objects.")
    records = dataset.get("records")  # type: ignore
    if not isinstance(records, list):
        raise JsonExportError("JSON export records must be an array.")
    if len(records) != expected_rows:  # type: ignore
        raise JsonExportError(
            "JSON export row count mismatch: "
            f"expected {expected_rows}, got {len(records)}"  # type: ignore
        )
    if not isinstance(dataset.get("schema_version"), str):  # type: ignore
        raise JsonExportError("JSON dataset schema version is missing.")


def _canonical_json_bytes(payload: dict[str, object]) -> bytes:  # type: ignore
    """Return the canonical JSON bytes used for deterministic hashing."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode(JSON_ENCODING)


__all__ = [
    "JSON_FORMAT",
    "JSON_SCHEMA_VERSION",
    "JsonExportError",
    "JsonExportResult",
    "verify_json",
    "write_json",
]
