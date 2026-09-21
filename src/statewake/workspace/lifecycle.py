"""Workspace lifecycle orchestration over existing StateWake lifecycle primitives."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..adapters.content_store import ContentAddressedArtifactStore
from ..adapters.retention import InMemoryEvidenceRetentionAdapter
from ..domain.data_lifecycle import (
    DataLifecycleDecision,
    DataLifecyclePolicy,
    DeletionRecord,
    assess_data_lifecycle,
)
from ..domain.retention import EvidenceRetentionRequirement
from .models import WorkspaceRecordIndexEntry, WorkspaceRetention
from .repository import StateWakeRepository


@dataclass(frozen=True, slots=True)
class WorkspaceLifecycleResult:
    """Describe one lifecycle operation without exposing payload bytes."""

    object_id: str
    action: str
    decision: DataLifecycleDecision
    deletion: DeletionRecord | None = None


class WorkspaceLifecycle:
    """Coordinate durable retention metadata with existing StateWake deletion adapters."""

    def __init__(
        self,
        workspace_root: Path,
        repository: StateWakeRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize lifecycle orchestration for one workspace."""
        self._repository = repository
        self._artifact_store = ContentAddressedArtifactStore(
            workspace_root / "artifacts"
        )
        self._export_root = workspace_root / "exports"
        self._clock = clock or (lambda: datetime.now(UTC))

    def apply_retention(
        self,
        record_id: str,
        policy: DataLifecyclePolicy,
        *,
        legal_hold: bool = False,
        now: datetime | None = None,
    ) -> WorkspaceRetention:
        """Persist a record retention requirement and legal-hold state."""
        record = self._require_record(record_id)
        effective_now = self._now(now)
        decision = assess_data_lifecycle(
            record_id,
            sensitivity=record.sensitivity,
            created_at=record.created_at,
            policy=policy,
            now=effective_now,
            legal_hold=legal_hold,
        )
        if decision.retain_until is not None:
            requirement = EvidenceRetentionRequirement(
                record.artifact_digest,
                datetime.fromisoformat(decision.retain_until),
                legal_hold=legal_hold,
                policy_id=policy.policy_id,
            )
            print(requirement)
        else:
            requirement = None
        self._repository.upsert_retention(
            object_id=record_id,
            policy_id=policy.policy_id,
            sensitivity=record.sensitivity,
            retain_until=decision.retain_until,
            legal_hold=legal_hold,
        )
        return WorkspaceRetention(
            object_id=record_id,
            policy_id=policy.policy_id,
            sensitivity=record.sensitivity,
            retain_until=decision.retain_until,
            legal_hold=legal_hold,
        )

    def evaluate_record(
        self,
        record_id: str,
        policy: DataLifecyclePolicy,
        *,
        now: datetime | None = None,
    ) -> DataLifecycleDecision:
        """Evaluate current retention, legal hold, storage, and disclosure semantics."""
        record = self._require_record(record_id)
        effective_now = self._now(now)
        retention = self._repository.get_retention(record_id)
        legal_hold = bool(retention and retention.legal_hold)
        return assess_data_lifecycle(
            record_id,
            sensitivity=record.sensitivity,
            created_at=record.created_at,
            policy=policy,
            now=effective_now,
            legal_hold=legal_hold,
        )

    def delete_expired_record(
        self,
        record_id: str,
        *,
        now: datetime | None = None,
        reason: str = "retention expired",
    ) -> WorkspaceLifecycleResult:
        """Delete one expired artifact through the existing retention-aware store."""
        record = self._require_record(record_id)
        retention = self._repository.get_retention(record_id)
        if retention is None:
            raise PermissionError(
                f"no durable retention policy is registered: {record_id}"
            )
        effective_now = self._now(now)
        policy = DataLifecyclePolicy(
            policy_id=retention.policy_id,
            purpose="workspace-data-lifecycle",
            storage_max_sensitivity="restricted",
            disclosure_max_sensitivity="restricted",
        )
        if retention.retain_until is not None:
            retain_until = datetime.fromisoformat(retention.retain_until)
            max_days = max(0, (retain_until - record.created_at.astimezone(UTC)).days)
            policy = DataLifecyclePolicy(
                policy_id=retention.policy_id,
                purpose="workspace-data-lifecycle",
                max_retention_days=max_days,
                storage_max_sensitivity="restricted",
                disclosure_max_sensitivity="restricted",
            )
        decision = assess_data_lifecycle(
            record_id,
            sensitivity=record.sensitivity,
            created_at=record.created_at,
            policy=policy,
            now=effective_now,
            legal_hold=retention.legal_hold,
        )
        if not decision.deletion_allowed:
            raise PermissionError(
                f"artifact deletion is blocked by lifecycle policy: {record_id}"
            )
        adapter = InMemoryEvidenceRetentionAdapter()
        if retention.retain_until is not None:
            adapter.require_retention(
                EvidenceRetentionRequirement(
                    record.artifact_digest,
                    datetime.fromisoformat(retention.retain_until),
                    legal_hold=retention.legal_hold,
                    policy_id=retention.policy_id,
                )
            )
        artifact_deletion = self._artifact_store.delete(
            record.artifact_digest,
            retention=adapter,
            now=effective_now,
            sensitivity=record.sensitivity,
            policy_id=record.policy_id,
            reason=reason,
        )
        deletion = DeletionRecord(
            object_id=record_id,
            digest=artifact_deletion.digest,
            sensitivity=artifact_deletion.sensitivity,
            deleted_at=artifact_deletion.deleted_at,
            policy_id=artifact_deletion.policy_id,
            reason=artifact_deletion.reason,
        )
        self._repository.record_deletion(deletion)
        return WorkspaceLifecycleResult(record_id, "delete", decision, deletion)

    def apply_export_retention(
        self,
        export_id: str,
        policy: DataLifecyclePolicy,
        *,
        sensitivity: str = "internal",
        legal_hold: bool = False,
        now: datetime | None = None,
    ) -> WorkspaceRetention:
        """Register lifecycle requirements for one workspace-controlled export."""
        export = self._repository.get_export(export_id)
        if export is None:
            raise KeyError(f"workspace export not found: {export_id}")
        effective_now = self._now(now)
        decision = assess_data_lifecycle(
            self._export_object_id(export_id),
            sensitivity=sensitivity,
            created_at=datetime.fromisoformat(export.created_at),
            policy=policy,
            now=effective_now,
            legal_hold=legal_hold,
        )
        self._repository.upsert_retention(
            object_id=self._export_object_id(export_id),
            policy_id=policy.policy_id,
            sensitivity=sensitivity,
            retain_until=decision.retain_until,
            legal_hold=legal_hold,
        )
        return WorkspaceRetention(
            object_id=self._export_object_id(export_id),
            policy_id=policy.policy_id,
            sensitivity=sensitivity,
            retain_until=decision.retain_until,
            legal_hold=legal_hold,
        )

    def delete_expired_export(
        self,
        export_id: str,
        *,
        now: datetime | None = None,
        reason: str = "retention expired",
    ) -> WorkspaceLifecycleResult:
        """Delete an expired workspace-controlled export and retain only its tombstone."""
        export = self._repository.get_export(export_id)
        if export is None:
            raise KeyError(f"workspace export not found: {export_id}")
        object_id = self._export_object_id(export_id)
        retention = self._repository.get_retention(object_id)
        if retention is None:
            raise PermissionError(
                f"no durable retention policy is registered: {object_id}"
            )
        effective_now = self._now(now)
        policy = DataLifecyclePolicy(
            policy_id=retention.policy_id,
            purpose="workspace-export-lifecycle",
            storage_max_sensitivity="restricted",
            disclosure_max_sensitivity="restricted",
        )
        if retention.retain_until is not None:
            created = datetime.fromisoformat(export.created_at)
            retain_until = datetime.fromisoformat(retention.retain_until)
            max_days = max(0, (retain_until - created.astimezone(UTC)).days)
            policy = DataLifecyclePolicy(
                policy_id=retention.policy_id,
                purpose="workspace-export-lifecycle",
                max_retention_days=max_days,
                storage_max_sensitivity="restricted",
                disclosure_max_sensitivity="restricted",
            )
        decision = assess_data_lifecycle(
            object_id,
            sensitivity=retention.sensitivity,
            created_at=datetime.fromisoformat(export.created_at),
            policy=policy,
            now=effective_now,
            legal_hold=retention.legal_hold,
        )
        if not decision.deletion_allowed:
            raise PermissionError(
                f"export deletion is blocked by lifecycle policy: {export_id}"
            )
        path = Path(export.output_path)
        if not self._is_managed_export_path(path):
            raise PermissionError(
                f"export path is outside the workspace export root: {path}"
            )
        if export.output_digest is None:
            raise PermissionError(f"export has no persisted output digest: {export_id}")
        if not path.is_file():
            raise FileNotFoundError(f"workspace export not found on disk: {path}")
        path.unlink()
        digest = export.output_digest
        deletion = DeletionRecord(
            object_id=object_id,
            digest=digest,
            sensitivity=retention.sensitivity,
            deleted_at=effective_now.astimezone(UTC).isoformat(),
            policy_id=retention.policy_id,
            reason=reason,
        )
        self._repository.record_deletion(deletion)
        return WorkspaceLifecycleResult(object_id, "delete-export", decision, deletion)

    def _require_record(self, record_id: str) -> WorkspaceRecordIndexEntry:
        """Return a persisted record or raise a typed lookup failure."""
        record = self._repository_record(record_id)
        if record is None:
            raise KeyError(f"workspace record not found: {record_id}")
        return record

    def _repository_record(self, record_id: str) -> WorkspaceRecordIndexEntry | None:
        """Load one canonical record through the workspace index boundary."""
        from .models import WorkspaceRecordQuery

        entries, _ = self._repository.query_records(
            WorkspaceRecordQuery(record_id=record_id, limit=1)
        )
        return entries[0] if entries else None

    def _now(self, value: datetime | None) -> datetime:
        """Return one timezone-aware lifecycle evaluation instant."""
        effective = self._clock() if value is None else value
        if effective.tzinfo is None:
            raise ValueError("now must be timezone-aware.")
        return effective

    def _is_managed_export_path(self, path: Path) -> bool:
        """Return whether an export path is contained within the workspace export root."""
        root = self._export_root.resolve()
        try:
            path.resolve().relative_to(root)
        except ValueError:
            return False
        return True

    @staticmethod
    def _export_object_id(export_id: str) -> str:
        """Namespace export lifecycle identities away from record identities."""
        return f"export:{export_id}"
