"""Workspace-level integrity and verification reporting."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ..adapters.content_store import ContentAddressedArtifactStore
from ..adapters.evidence_ingestion import (
    JsonEvidenceReceiptStore,
    LocalEvidenceIngestionAdapter,
)
from ..domain.data_lifecycle import DeletionRecord
from .models import WorkspaceExport, WorkspaceIdentity, WorkspaceRecordIndexEntry
from .repository import WorkspaceIntegritySnapshot

WorkspaceVerificationStatus = Literal[
    "healthy",
    "healthy with limitations",
    "incomplete",
    "invalid",
    "corrupt",
]


@dataclass(frozen=True, slots=True)
class WorkspaceVerificationIssue:
    """Describe one integrity finding using stable, machine-readable severity."""

    code: str
    severity: Literal["warning", "error"]
    message: str
    object_id: str | None = None
    path: str | None = None


@dataclass(frozen=True, slots=True)
class WorkspaceVerificationReport:
    """Summarize workspace integrity findings and bounded verification counts."""

    status: WorkspaceVerificationStatus
    issues: tuple[WorkspaceVerificationIssue, ...]
    checked_records: int = 0
    checked_receipts: int = 0
    checked_artifacts: int = 0
    checked_exports: int = 0
    orphan_artifacts: tuple[str, ...] = ()
    orphan_receipts: tuple[str, ...] = ()
    orphan_exports: tuple[str, ...] = ()

    @property
    def healthy(self) -> bool:
        """Return whether verification found no integrity errors."""
        return self.status in {"healthy", "healthy with limitations"}

    @property
    def has_errors(self) -> bool:
        """Return whether verification found at least one integrity error."""
        return any(issue.severity == "error" for issue in self.issues)


class WorkspaceVerifier:
    """Verify workspace metadata while delegating evidence checks to StateWake."""

    def __init__(self, workspace_root: Path) -> None:
        """Initialize verification against one workspace filesystem root."""
        self._root = workspace_root
        self._artifact_store = ContentAddressedArtifactStore(
            workspace_root / "artifacts"
        )
        self._receipt_store = JsonEvidenceReceiptStore(workspace_root / "receipts")
        self._ingestion = LocalEvidenceIngestionAdapter(
            self._artifact_store,
            self._receipt_store,
        )

    def verify(
        self,
        *,
        identity: WorkspaceIdentity,
        manifest_path: Path,
        repository_snapshot: WorkspaceIntegritySnapshot,
    ) -> WorkspaceVerificationReport:
        """Verify schema, references, canonical evidence, manifest, and exports."""
        issues: list[WorkspaceVerificationIssue] = []
        self._verify_manifest(identity, manifest_path, issues)
        record_ids = {record.record_id for record in repository_snapshot.records}
        deleted = {
            item.object_id: item for item in repository_snapshot.deletion_records
        }
        self._verify_reference_consistency(
            repository_snapshot, record_ids, deleted, issues
        )
        checked_receipts, checked_artifacts = self._verify_records(
            repository_snapshot.records,
            deleted,
            issues,
        )
        orphan_artifacts = self._find_orphan_artifacts(repository_snapshot.records)
        orphan_receipts = self._find_orphan_receipts(repository_snapshot.records)
        orphan_exports = self._verify_exports(
            repository_snapshot.exports, deleted, issues
        )
        for path in orphan_artifacts:
            issues.append(
                WorkspaceVerificationIssue(
                    "ORPHAN_ARTIFACT",
                    "warning",
                    "artifact exists without a canonical workspace record.",
                    path=path,
                )
            )
        for path in orphan_receipts:
            issues.append(
                WorkspaceVerificationIssue(
                    "ORPHAN_RECEIPT",
                    "warning",
                    "receipt exists without a canonical workspace record.",
                    path=path,
                )
            )
        status = _status_for(issues)
        return WorkspaceVerificationReport(
            status=status,
            issues=tuple(issues),
            checked_records=len(repository_snapshot.records),
            checked_receipts=checked_receipts,
            checked_artifacts=checked_artifacts,
            checked_exports=len(repository_snapshot.exports),
            orphan_artifacts=orphan_artifacts,
            orphan_receipts=orphan_receipts,
            orphan_exports=orphan_exports,
        )

    @staticmethod
    def _verify_manifest(
        identity: WorkspaceIdentity,
        manifest_path: Path,
        issues: list[WorkspaceVerificationIssue],
    ) -> None:
        """Verify manifest identity without replacing the canonical manifest parser."""
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            issues.append(
                WorkspaceVerificationIssue(
                    "MANIFEST_UNREADABLE",
                    "error",
                    f"workspace manifest could not be read: {exc}",
                    path=str(manifest_path),
                )
            )
            return
        if not isinstance(payload, dict):
            issues.append(
                WorkspaceVerificationIssue(
                    "MANIFEST_INVALID",
                    "error",
                    "workspace manifest must contain a JSON object.",
                    path=str(manifest_path),
                )
            )
            return
        expected = {
            "workspace_id": identity.workspace_id,
            "created_at": identity.created_at,
            "schema_version": identity.schema_version,
            "public_api_contract_version": identity.statewake_public_api_contract_version,
        }
        for field, value in expected.items():
            if payload.get(field) != value:
                issues.append(
                    WorkspaceVerificationIssue(
                        "MANIFEST_MISMATCH",
                        "error",
                        f"manifest field {field!r} does not match the workspace identity.",
                        path=str(manifest_path),
                    )
                )
        if payload.get("storage_backend") != "sqlite":
            issues.append(
                WorkspaceVerificationIssue(
                    "MANIFEST_BACKEND_MISMATCH",
                    "error",
                    "manifest storage_backend is not the supported SQLite backend.",
                    path=str(manifest_path),
                )
            )

    @staticmethod
    def _verify_reference_consistency(
        snapshot: WorkspaceIntegritySnapshot,
        record_ids: set[str],
        deleted: dict[str, DeletionRecord],
        issues: list[WorkspaceVerificationIssue],
    ) -> None:
        """Check relationships and lifecycle references for dangling objects."""
        for record in snapshot.records:
            if record.run_id is not None and record.run_id not in snapshot.run_ids:
                issues.append(
                    WorkspaceVerificationIssue(
                        "DANGLING_RUN_REFERENCE",
                        "error",
                        "record references a missing run.",
                        object_id=record.record_id,
                    )
                )
        known_objects = record_ids | {
            f"export:{item.export_id}" for item in snapshot.exports
        }
        for source_id, target_id, _relationship_type in snapshot.relationship_rows:
            if source_id not in known_objects or target_id not in known_objects:
                issues.append(
                    WorkspaceVerificationIssue(
                        "DANGLING_RELATIONSHIP",
                        "error",
                        "relationship references an unknown workspace object.",
                        object_id=source_id,
                    )
                )
        for subject_id in snapshot.state_transition_subject_ids:
            if subject_id not in known_objects:
                issues.append(
                    WorkspaceVerificationIssue(
                        "DANGLING_STATE_TRANSITION",
                        "error",
                        "state transition references an unknown workspace object.",
                        object_id=subject_id,
                    )
                )
        for object_id in snapshot.retention_object_ids:
            if object_id not in known_objects:
                issues.append(
                    WorkspaceVerificationIssue(
                        "DANGLING_RETENTION",
                        "error",
                        "retention metadata references an unknown workspace object.",
                        object_id=object_id,
                    )
                )
        for deletion in deleted.values():
            if deletion.object_id not in known_objects:
                issues.append(
                    WorkspaceVerificationIssue(
                        "DANGLING_DELETION",
                        "error",
                        "deletion tombstone references an unknown workspace object.",
                        object_id=deletion.object_id,
                    )
                )

    def _verify_records(
        self,
        records: tuple[WorkspaceRecordIndexEntry, ...],
        deleted: dict[str, DeletionRecord],
        issues: list[WorkspaceVerificationIssue],
    ) -> tuple[int, int]:
        """Verify persisted receipts and non-deleted canonical artifact payloads."""
        checked_receipts = 0
        checked_artifacts = 0
        for record in records:
            try:
                receipt = self._receipt_store.get(record.receipt_id)
                checked_receipts += 1
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                issues.append(
                    WorkspaceVerificationIssue(
                        "RECEIPT_INVALID",
                        "error",
                        f"canonical receipt could not be loaded: {exc}",
                        object_id=record.record_id,
                    )
                )
                continue
            if not _receipt_matches_entry(receipt, record):
                issues.append(
                    WorkspaceVerificationIssue(
                        "RECEIPT_REFERENCE_MISMATCH",
                        "error",
                        "persisted receipt does not match the operational index.",
                        object_id=record.record_id,
                    )
                )
                continue
            artifact_path = (
                self._root
                / "artifacts"
                / record.artifact_digest[:2]
                / record.artifact_digest[2:]
            )
            receipt_path = self._root / "receipts" / f"{record.receipt_id}.json"
            if artifact_path.is_symlink():
                issues.append(
                    WorkspaceVerificationIssue(
                        "ARTIFACT_SYMLINK",
                        "error",
                        "canonical artifact path must not be a symlink.",
                        object_id=record.record_id,
                        path=str(artifact_path),
                    )
                )
                continue
            if receipt_path.is_symlink():
                issues.append(
                    WorkspaceVerificationIssue(
                        "RECEIPT_SYMLINK",
                        "error",
                        "canonical receipt path must not be a symlink.",
                        object_id=record.record_id,
                        path=str(receipt_path),
                    )
                )
                continue
            tombstone = deleted.get(record.record_id)
            if tombstone is not None:
                if tombstone.digest != record.artifact_digest:
                    issues.append(
                        WorkspaceVerificationIssue(
                            "DELETION_DIGEST_MISMATCH",
                            "error",
                            "deletion tombstone digest does not match the indexed artifact.",
                            object_id=record.record_id,
                        )
                    )
                if self._artifact_store.exists(record.artifact_digest):
                    issues.append(
                        WorkspaceVerificationIssue(
                            "DELETED_ARTIFACT_PRESENT",
                            "error",
                            "artifact remains present despite a deletion tombstone.",
                            object_id=record.record_id,
                        )
                    )
                continue
            try:
                self._ingestion.verify(receipt)
                checked_artifacts += 1
            except FileNotFoundError as exc:
                issues.append(
                    WorkspaceVerificationIssue(
                        "ARTIFACT_MISSING",
                        "error",
                        f"referenced artifact is missing: {exc}",
                        object_id=record.record_id,
                    )
                )
            except (OSError, ValueError, TypeError) as exc:
                issues.append(
                    WorkspaceVerificationIssue(
                        "EVIDENCE_INVALID",
                        "error",
                        f"canonical evidence verification failed: {exc}",
                        object_id=record.record_id,
                    )
                )
        return checked_receipts, checked_artifacts

    def _verify_exports(
        self,
        exports: tuple[WorkspaceExport, ...],
        deleted: dict[str, DeletionRecord],
        issues: list[WorkspaceVerificationIssue],
    ) -> tuple[str, ...]:
        """Check persisted export metadata, paths, and output identities."""
        orphan: list[str] = []
        expected_files: set[Path] = set()
        root = (self._root / "exports").resolve()
        for export in exports:
            object_id = f"export:{export.export_id}"
            try:
                query = json.loads(export.query_definition_json)
            except (TypeError, json.JSONDecodeError):
                issues.append(
                    WorkspaceVerificationIssue(
                        "EXPORT_METADATA_INVALID",
                        "error",
                        "export query definition is not valid JSON.",
                        object_id=object_id,
                    )
                )
                query = None
            if query is not None and not isinstance(query, dict):
                issues.append(
                    WorkspaceVerificationIssue(
                        "EXPORT_METADATA_INVALID",
                        "error",
                        "export query definition must be a JSON object.",
                        object_id=object_id,
                    )
                )
            path = Path(export.output_path)
            try:
                resolved = path.resolve()
                resolved.relative_to(root)
            except (OSError, ValueError):
                issues.append(
                    WorkspaceVerificationIssue(
                        "EXPORT_PATH_OUTSIDE_ROOT",
                        "error",
                        "export output path is outside the workspace export root.",
                        object_id=object_id,
                        path=str(path),
                    )
                )
                continue
            tombstone = deleted.get(object_id)
            if tombstone is not None:
                if path.exists():
                    issues.append(
                        WorkspaceVerificationIssue(
                            "DELETED_EXPORT_PRESENT",
                            "error",
                            "export remains present despite a deletion tombstone.",
                            object_id=object_id,
                            path=str(path),
                        )
                    )
                continue
            if not path.exists():
                issues.append(
                    WorkspaceVerificationIssue(
                        "EXPORT_MISSING",
                        "error",
                        "persisted export metadata references a missing output.",
                        object_id=object_id,
                        path=str(path),
                    )
                )
                continue
            expected_files.update(_contained_files(path))
            if export.output_digest is None or not _is_sha256(export.output_digest):
                issues.append(
                    WorkspaceVerificationIssue(
                        "EXPORT_DIGEST_INVALID",
                        "error",
                        "export output digest is missing or malformed.",
                        object_id=object_id,
                    )
                )
                continue
            actual = _sha256_path(path)
            if actual != export.output_digest:
                issues.append(
                    WorkspaceVerificationIssue(
                        "EXPORT_DIGEST_MISMATCH",
                        "error",
                        "export output digest does not match persisted metadata.",
                        object_id=object_id,
                        path=str(path),
                    )
                )
            if export.row_count is None or export.row_count < 0:
                issues.append(
                    WorkspaceVerificationIssue(
                        "EXPORT_ROW_COUNT_INVALID",
                        "error",
                        "export row count is missing or negative.",
                        object_id=object_id,
                    )
                )
        for item in self._root.glob("exports/**/*"):
            if not item.is_file() or item.name.endswith(".tmp"):
                continue
            try:
                item.resolve().relative_to(root)
            except ValueError:
                continue
            if item.resolve() not in expected_files:
                orphan.append(str(item))
        return tuple(sorted(orphan))

    def _find_orphan_artifacts(
        self, records: tuple[WorkspaceRecordIndexEntry, ...]
    ) -> tuple[str, ...]:
        """Return artifact files not referenced by indexed records or deletion history."""
        expected = {
            self._root.joinpath(
                "artifacts", record.artifact_digest[:2], record.artifact_digest[2:]
            ).resolve()
            for record in records
        }
        orphan: list[str] = []
        for item in self._root.joinpath("artifacts").glob("**/*"):
            if item.is_symlink():
                orphan.append(str(item))
                continue
            if not item.is_file() or item.name.endswith(".tmp"):
                continue
            if item.resolve() not in expected:
                orphan.append(str(item))
        return tuple(sorted(orphan))

    def _find_orphan_receipts(
        self, records: tuple[WorkspaceRecordIndexEntry, ...]
    ) -> tuple[str, ...]:
        """Return persisted receipt files not referenced by indexed records."""
        expected = {
            (self._root / "receipts" / f"{record.receipt_id}.json").resolve()
            for record in records
        }
        orphan: list[str] = []
        for item in self._root.joinpath("receipts").glob("*.json"):
            if item.is_symlink() or item.resolve() not in expected:
                orphan.append(str(item))
        return tuple(sorted(orphan))


def _receipt_matches_entry(receipt: object, entry: WorkspaceRecordIndexEntry) -> bool:
    """Compare all index fields duplicated from the canonical evidence receipt."""
    captured_at = getattr(receipt, "captured_at", None)
    if captured_at is None or captured_at.tzinfo is None:
        return False
    return (
        getattr(receipt, "receipt_id", None) == entry.receipt_id
        and getattr(receipt, "artifact_digest", None) == entry.artifact_digest
        and getattr(receipt, "artifact_size", None) == entry.artifact_size
        and getattr(receipt, "producer_id", None) == entry.producer_id
        and getattr(receipt, "producer_type", None) == entry.producer_type
        and getattr(receipt, "producer_version", None) == entry.producer_version
        and getattr(receipt, "source_ref", None) == entry.source_ref
        and getattr(receipt, "source_event_id", None) == entry.source_event_id
        and getattr(receipt, "run_id", None) == entry.run_id
        and captured_at.astimezone(entry.captured_at.tzinfo) == entry.captured_at
    )


def _contained_files(path: Path) -> set[Path]:
    """Return all file members represented by one export path."""
    if path.is_file():
        return {path.resolve()}
    return {item.resolve() for item in path.rglob("*") if item.is_file()}


def _sha256_path(path: Path) -> str:
    """Hash a file or deterministic directory dataset using stored export semantics."""
    digest = hashlib.sha256()
    if path.is_file():
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    for item in sorted(path.rglob("*")):
        if item.is_file():
            relative = item.relative_to(path)
            digest.update(relative.as_posix().encode("utf-8"))
            digest.update(b"\0")
            with item.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
    return digest.hexdigest()


def _is_sha256(value: str) -> bool:
    """Return whether a value is a lowercase SHA-256 digest."""
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _status_for(
    issues: list[WorkspaceVerificationIssue],
) -> WorkspaceVerificationStatus:
    """Derive the contract status from ordered finding severity."""
    if not issues:
        return "healthy"
    if any(item.code in {"MANIFEST_UNREADABLE"} for item in issues):
        return "corrupt"
    if any(item.severity == "error" for item in issues):
        if any(item.code in {"ARTIFACT_MISSING", "EXPORT_MISSING"} for item in issues):
            return "incomplete"
        return "invalid"
    return "healthy with limitations"


__all__ = [
    "WorkspaceVerificationIssue",
    "WorkspaceVerificationReport",
    "WorkspaceVerificationStatus",
    "WorkspaceVerifier",
]
