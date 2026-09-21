"""Portable StateWake dataset bundles distinct from reliability proof bundles."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from zipfile import ZipFile

from ..domain.operations import write_deterministic_zip
from .models import WorkspaceRecord
from .projections import DatasetProjection

BUNDLE_FORMAT = "statewake-portable-dataset"
BUNDLE_SCHEMA_VERSION = "1"


class PortableBundleError(ValueError):
    """Raised when a portable dataset bundle is invalid or unsafe."""


@dataclass(frozen=True, slots=True)
class PortableBundleResult:
    """Describe one completed portable StateWake dataset bundle."""

    export_id: str
    output_path: Path
    output_digest: str
    row_count: int
    schema_version: str
    disclosure_max_sensitivity: str


def write_portable_bundle(
    projection: DatasetProjection,
    records: tuple[WorkspaceRecord, ...],
    output: Path,
    *,
    workspace_id: str,
    schema_version: str,
    disclosure_max_sensitivity: str,
    query_definition: dict[str, object],
    created_at: datetime,
) -> PortableBundleResult:
    """Write a self-describing dataset bundle with checksummed members."""
    if created_at.tzinfo is None:
        raise PortableBundleError("created_at must be timezone-aware.")
    if len(records) != len(projection.records):
        raise PortableBundleError("projection and record counts must match.")
    dataset_bytes = (
        _canonical_json_bytes(
            {
                "format": "json",
                "schema_version": schema_version,
                "disclosure_max_sensitivity": disclosure_max_sensitivity,
                "query": query_definition,
                "dataset": projection.to_dict(),
            }
        )
        + b"\n"
    )
    receipts_bytes = b"".join(
        (
            json.dumps(
                record.receipt.to_dict(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        for record in records
    )
    state_bytes = b"".join(
        (
            _canonical_json_bytes(
                {
                    "record_id": record.record_id,
                    "verification_status": record.verification_status,
                    "reliability_state": record.reliability_state,
                }
            )
            + b"\n"
        )
        for record in records
    )
    member_payloads = {
        "dataset.json": dataset_bytes,
        "receipts.jsonl": receipts_bytes,
        "state.jsonl": state_bytes,
    }
    checksums = {
        name: sha256(content).hexdigest()
        for name, content in sorted(member_payloads.items())
    }
    manifest = {
        "format": BUNDLE_FORMAT,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "workspace_id": workspace_id,
        "source_schema_version": schema_version,
        "disclosure_max_sensitivity": disclosure_max_sensitivity,
        "query": query_definition,
        "created_at": created_at.astimezone(UTC).isoformat(),
        "row_count": len(records),
        "dataset_export_type": "structured-dataset",
        "proof_bundle": False,
        "members": sorted(member_payloads),
        "checksums_file": "checksums.json",
    }
    manifest_bytes = _canonical_json_bytes(dict(manifest)) + b"\n"
    checksum_bytes = _canonical_json_bytes(checksums) + b"\n"
    readme = (
        b"StateWake portable dataset bundle.\n"
        b"This is a structured dataset export, not a reliability proof package.\n"
        b"Verify member checksums before consuming exported data.\n"
    )
    files = {
        "manifest.json": manifest_bytes,
        "dataset.json": dataset_bytes,
        "receipts.jsonl": receipts_bytes,
        "state.jsonl": state_bytes,
        "checksums.json": checksum_bytes,
        "README.md": readme,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(f".{output.name}.tmp")
    try:
        write_deterministic_zip(files, temp)
        os.replace(temp, output)
    except OSError as exc:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass
        raise PortableBundleError(f"unable to write portable bundle: {exc}") from exc
    digest = _sha256_file(output)
    return PortableBundleResult(
        export_id=digest,
        output_path=output,
        output_digest=digest,
        row_count=len(records),
        schema_version=schema_version,
        disclosure_max_sensitivity=disclosure_max_sensitivity,
    )


def verify_portable_bundle(
    path: Path,
    *,
    expected_rows: int,
    expected_schema_version: str,
    expected_workspace_id: str,
) -> None:
    """Verify the portable dataset envelope and member checksums."""
    if not path.is_file():
        raise PortableBundleError(f"portable bundle does not exist: {path}")
    with ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise PortableBundleError("portable bundle contains duplicate members.")
        required = {
            "manifest.json",
            "dataset.json",
            "receipts.jsonl",
            "state.jsonl",
            "checksums.json",
            "README.md",
        }
        if set(names) != required:
            raise PortableBundleError("portable bundle member set is invalid.")
        manifest = _load_object(archive.read("manifest.json"))
        if manifest.get("format") != BUNDLE_FORMAT:
            raise PortableBundleError("portable bundle format marker is invalid.")
        if manifest.get("schema_version") != BUNDLE_SCHEMA_VERSION:
            raise PortableBundleError("portable bundle schema version is invalid.")
        if manifest.get("workspace_id") != expected_workspace_id:
            raise PortableBundleError("portable bundle workspace identity is invalid.")
        if manifest.get("source_schema_version") != expected_schema_version:
            raise PortableBundleError(
                "portable bundle source schema version is invalid."
            )
        if manifest.get("proof_bundle") is not False:
            raise PortableBundleError(
                "dataset bundle must not masquerade as proof bundle."
            )
        if manifest.get("row_count") != expected_rows:
            raise PortableBundleError("portable bundle row count is invalid.")
        checksums = _load_object(archive.read("checksums.json"))
        for name in ("dataset.json", "receipts.jsonl", "state.jsonl"):
            actual = sha256(archive.read(name)).hexdigest()
            if checksums.get(name) != actual:
                raise PortableBundleError(f"checksum mismatch for {name}.")
        dataset = _load_object(archive.read("dataset.json"))
        if dataset.get("schema_version") != expected_schema_version:
            raise PortableBundleError("portable dataset schema version is invalid.")
        dataset_payload = dataset.get("dataset")
        rows = (
            dataset_payload.get("records")
            if isinstance(dataset_payload, dict)
            else None
        )
        if not isinstance(rows, list) or len(rows) != expected_rows:
            raise PortableBundleError("portable dataset record count is invalid.")
        receipt_rows = archive.read("receipts.jsonl").splitlines()
        state_rows = archive.read("state.jsonl").splitlines()
        if len(receipt_rows) != expected_rows or len(state_rows) != expected_rows:
            raise PortableBundleError(
                "portable bundle reference row counts are invalid."
            )


def _canonical_json_bytes(payload: Mapping[str, object]) -> bytes:
    """Return canonical JSON bytes for deterministic bundle members."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _load_object(raw: bytes) -> dict[str, object]:
    """Decode one JSON object from bundle bytes."""
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PortableBundleError("portable bundle contains invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise PortableBundleError("portable bundle JSON member must be an object.")
    return payload


def _sha256_file(path: Path) -> str:
    """Hash a file with a fixed block size."""
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "BUNDLE_FORMAT",
    "BUNDLE_SCHEMA_VERSION",
    "PortableBundleError",
    "PortableBundleResult",
    "verify_portable_bundle",
    "write_portable_bundle",
]
