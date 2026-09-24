"""Workspace backup restore with checksum verification and staged replacement."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

from .backup import BACKUP_FORMAT, BACKUP_SCHEMA_VERSION
from .integrity_sweep import sweep_workspace_payload_integrity

_BACKUP_MANIFEST = "backup-manifest.json"
_CHECKSUMS = "checksums.json"
_MAX_BACKUP_MEMBER_BYTES = 2 * 1024 * 1024 * 1024
_MAX_BACKUP_TOTAL_BYTES = 8 * 1024 * 1024 * 1024


class WorkspaceRestoreError(ValueError):
    """Raised when a workspace backup cannot be restored safely."""


@dataclass(frozen=True, slots=True)
class WorkspaceRestoreResult:
    """Describe one restored workspace directory."""

    workspace_root: Path
    workspace_id: str
    schema_version: str
    restored_files: int


def restore_workspace_backup(
    backup_path: Path,
    target_root: Path,
    *,
    overwrite: bool = False,
) -> WorkspaceRestoreResult:
    """Stage a verified backup, then replace the exact destination tree.

    Replacement requires an inactive workspace; callers must not write to or
    open the destination concurrently with this operation.  A failed staged
    extraction leaves the existing workspace untouched.
    """
    if target_root.is_symlink() or any(
        parent.is_symlink() for parent in target_root.parents
    ):
        raise WorkspaceRestoreError("restore destination cannot traverse a symlink")
    if target_root.exists() and not target_root.is_dir():
        raise WorkspaceRestoreError("restore destination must be a directory")
    if target_root.exists() and any(target_root.iterdir()) and not overwrite:
        raise WorkspaceRestoreError("target workspace root is not empty.")
    manifest, _checksums, members = _read_verified_backup(backup_path)
    target_root.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".statewake-restore-", dir=target_root.parent))
    previous: Path | None = None
    try:
        with ZipFile(backup_path) as archive:
            for name in members:
                _validate_member_name(name)
                destination = stage.joinpath(*PurePosixPath(name).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(name) as source, destination.open("xb") as sink:
                    shutil.copyfileobj(source, sink)
        sweep_workspace_payload_integrity(stage)
        if target_root.exists():
            previous = Path(
                tempfile.mkdtemp(prefix=".statewake-previous-", dir=target_root.parent)
            )
            previous.rmdir()
            os.replace(target_root, previous)
        try:
            os.replace(stage, target_root)
        except OSError:
            if previous is not None:
                os.replace(previous, target_root)
                previous = None
            raise
        if previous is not None:
            shutil.rmtree(previous)
            previous = None
    except (OSError, ValueError) as exc:
        if isinstance(exc, WorkspaceRestoreError):
            raise
        raise WorkspaceRestoreError(f"workspace restore failed: {exc}") from exc
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return WorkspaceRestoreResult(
        workspace_root=target_root,
        workspace_id=str(manifest["workspace_id"]),
        schema_version=str(manifest["source_schema_version"]),
        restored_files=len(members),
    )


def _read_verified_backup(
    backup_path: Path,
) -> tuple[dict[str, object], dict[str, object], tuple[str, ...]]:
    if not backup_path.is_file():
        raise WorkspaceRestoreError(f"backup file does not exist: {backup_path}")
    with ZipFile(backup_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise WorkspaceRestoreError("backup contains duplicate members.")
        if _BACKUP_MANIFEST not in names or _CHECKSUMS not in names:
            raise WorkspaceRestoreError("backup is missing required manifest members.")
        manifest = _load_object(archive.read(_BACKUP_MANIFEST))
        checksums = _load_object(archive.read(_CHECKSUMS))
        if manifest.get("format") != BACKUP_FORMAT:
            raise WorkspaceRestoreError("backup format marker is invalid.")
        if manifest.get("schema_version") != BACKUP_SCHEMA_VERSION:
            raise WorkspaceRestoreError("backup schema version is invalid.")
        members_raw = manifest.get("members")
        if not isinstance(members_raw, list) or not all(
            isinstance(item, str) for item in members_raw
        ):
            raise WorkspaceRestoreError("backup member list is invalid.")
        members = tuple(members_raw)
        expected_names = set(members) | {_BACKUP_MANIFEST, _CHECKSUMS}
        if set(names) != expected_names or len(members) != len(set(members)):
            raise WorkspaceRestoreError("backup member set does not match manifest.")
        if manifest.get("file_count") != len(members):
            raise WorkspaceRestoreError("backup file count does not match manifest.")
        total_size = 0
        for info in archive.infolist():
            # A Unix symlink entry is not a regular backup file.
            if info.is_dir() or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise WorkspaceRestoreError("backup contains a non-file member.")
            if info.file_size > _MAX_BACKUP_MEMBER_BYTES:
                raise WorkspaceRestoreError("backup member exceeds size limit.")
            total_size += info.file_size
            if total_size > _MAX_BACKUP_TOTAL_BYTES:
                raise WorkspaceRestoreError("backup exceeds total size limit.")
        for name in members:
            _validate_member_name(name)
            actual = hashlib.sha256(archive.read(name)).hexdigest()
            if checksums.get(name) != actual:
                raise WorkspaceRestoreError(f"backup checksum mismatch for {name}.")
    return manifest, checksums, members


def _validate_member_name(name: str) -> None:
    path = PurePosixPath(name)
    if (
        not name
        or name.startswith("/")
        or "\\" in name
        or ":" in path.parts[0]
        or ".." in path.parts
        or "." in path.parts
        or path.as_posix() != name
        or name in {_BACKUP_MANIFEST, _CHECKSUMS}
    ):
        raise WorkspaceRestoreError(f"unsafe backup member path: {name}")


def _load_object(raw: bytes) -> dict[str, object]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkspaceRestoreError("backup contains invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise WorkspaceRestoreError("backup JSON member must be an object.")
    return payload


__all__ = [
    "WorkspaceRestoreError",
    "WorkspaceRestoreResult",
    "restore_workspace_backup",
]
