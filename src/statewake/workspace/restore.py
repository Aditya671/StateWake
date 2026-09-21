"""Workspace backup restore and verification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

from .backup import BACKUP_FORMAT, BACKUP_SCHEMA_VERSION
from .integrity_sweep import sweep_workspace_payload_integrity

_BACKUP_MANIFEST = "backup-manifest.json"
_CHECKSUMS = "checksums.json"


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
    """Restore a verified workspace backup to an empty target directory."""
    manifest, checksums, members = _read_verified_backup(backup_path)
    if target_root.exists() and any(target_root.iterdir()) and not overwrite:
        raise WorkspaceRestoreError("target workspace root is not empty.")
    target_root.mkdir(parents=True, exist_ok=True)
    with ZipFile(backup_path) as archive:
        for name in members:
            _validate_member_name(name)
            target = target_root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
    sweep_workspace_payload_integrity(target_root)
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
        if set(names) != expected_names:
            raise WorkspaceRestoreError("backup member set does not match manifest.")
        if manifest.get("file_count") != len(members):
            raise WorkspaceRestoreError("backup file count does not match manifest.")
        for name in members:
            _validate_member_name(name)
            import hashlib

            actual = hashlib.sha256(archive.read(name)).hexdigest()
            if checksums.get(name) != actual:
                raise WorkspaceRestoreError(f"backup checksum mismatch for {name}.")
    return manifest, checksums, members


def _validate_member_name(name: str) -> None:
    path = Path(name)
    if name.startswith("/") or ".." in path.parts or name.strip() == "":
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
