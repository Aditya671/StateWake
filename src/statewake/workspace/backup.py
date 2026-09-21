"""Durable workspace backup creation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

BACKUP_FORMAT = "statewake-workspace-backup"
BACKUP_SCHEMA_VERSION = "1"
_BACKUP_MANIFEST = "backup-manifest.json"
_CHECKSUMS = "checksums.json"
_EXCLUDED_SUFFIXES = {".lock"}


class WorkspaceBackupError(ValueError):
    """Raised when a workspace backup cannot be created or verified."""


@dataclass(frozen=True, slots=True)
class WorkspaceBackupResult:
    """Describe one completed workspace backup artifact."""

    output_path: Path
    output_digest: str
    workspace_id: str
    schema_version: str
    file_count: int
    created_at: str


def create_workspace_backup(
    workspace_root: Path,
    output: Path,
    *,
    workspace_id: str,
    schema_version: str,
    created_at: datetime | None = None,
) -> WorkspaceBackupResult:
    """Create a deterministic ZIP backup of the durable workspace directory."""
    if not workspace_root.is_dir():
        raise WorkspaceBackupError(f"workspace root does not exist: {workspace_root}")
    timestamp = created_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise WorkspaceBackupError("created_at must be timezone-aware.")
    files = _collect_workspace_files(workspace_root, output.resolve())
    checksums = {name: sha256(path.read_bytes()).hexdigest() for name, path in files}
    manifest = {
        "format": BACKUP_FORMAT,
        "schema_version": BACKUP_SCHEMA_VERSION,
        "workspace_id": workspace_id,
        "source_schema_version": schema_version,
        "created_at": timestamp.astimezone(UTC).isoformat(),
        "file_count": len(files),
        "checksums_file": _CHECKSUMS,
        "members": [name for name, _path in files],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(f".{output.name}.tmp")
    try:
        with ZipFile(temp, "w", compression=ZIP_DEFLATED) as archive:
            _writestr(archive, _BACKUP_MANIFEST, _canonical_json(manifest) + b"\n")
            _writestr(archive, _CHECKSUMS, _canonical_json(checksums) + b"\n")
            for name, path in files:
                _writestr(archive, name, path.read_bytes())
        os.replace(temp, output)
    except OSError as exc:
        temp.unlink(missing_ok=True)
        raise WorkspaceBackupError(f"unable to create workspace backup: {exc}") from exc
    return WorkspaceBackupResult(
        output_path=output,
        output_digest=_sha256_file(output),
        workspace_id=workspace_id,
        schema_version=schema_version,
        file_count=len(files),
        created_at=str(manifest["created_at"]),
    )


def _collect_workspace_files(
    workspace_root: Path, output_path: Path
) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for path in sorted(workspace_root.rglob("*")):
        if not path.is_file():
            continue
        if path.resolve() == output_path:
            continue
        if path.name.startswith(".") and path.suffix == ".tmp":
            continue
        if path.suffix in _EXCLUDED_SUFFIXES:
            continue
        if any(part == "locks" for part in path.relative_to(workspace_root).parts):
            continue
        relative = path.relative_to(workspace_root).as_posix()
        files.append((relative, path))
    return files


def _canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _writestr(archive: ZipFile, name: str, payload: bytes) -> None:
    info = ZipInfo(name)
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, payload)


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


__all__ = [
    "BACKUP_FORMAT",
    "BACKUP_SCHEMA_VERSION",
    "WorkspaceBackupError",
    "WorkspaceBackupResult",
    "create_workspace_backup",
]
