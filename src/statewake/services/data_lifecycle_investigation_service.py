"""Strict read-side reconstruction of StateWake data-lifecycle governance context."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from statewake.domain.data_lifecycle import (
    DataLifecycleDecision,
    DataLifecyclePolicy,
    DeletionRecord,
    assess_data_lifecycle,
)
from statewake.domain.governance import SENSITIVITY_ORDER
from statewake.workspace.models import WorkspaceRecordQuery, WorkspaceRetention
from statewake.workspace.workspace import StateWakeWorkspace

DATA_LIFECYCLE_CONTEXT_SCHEMA_VERSION = "data-lifecycle-context.v1"
_DATA_LIFECYCLE_OBJECT_KINDS = frozenset({"workspace-record", "workspace-export"})


@dataclass(frozen=True, slots=True)
class RecordedDataLifecycleDecision:
    """One recorded lifecycle decision plus the exact evaluation timestamp."""

    evaluated_at: datetime
    decision: DataLifecycleDecision


@dataclass(frozen=True, slots=True)
class DataLifecycleContext:
    """Explicit lifecycle policy context for one workspace-controlled object."""

    object_kind: str
    object_id: str
    sensitivity: str
    created_at: datetime
    legal_hold: bool
    policy: DataLifecyclePolicy
    recorded_decision: RecordedDataLifecycleDecision | None = None


@dataclass(frozen=True, slots=True)
class ResolvedDataLifecycleContext:
    """Cross-checked lifecycle context bound to durable workspace metadata."""

    context: DataLifecycleContext
    retention: WorkspaceRetention
    deletion: DeletionRecord | None
    original_digest: str | None
    current_decision: DataLifecycleDecision


def _read_object(path: Path, *, max_bytes: int) -> dict[str, Any]:
    """Read one bounded UTF-8 JSON object without following symlinks."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    expanded = path.expanduser()
    if expanded.is_symlink() or any(parent.is_symlink() for parent in expanded.parents):
        raise ValueError("data lifecycle context path cannot traverse a symlink")
    with expanded.open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise OverflowError("data lifecycle context exceeds configured byte limit")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("data lifecycle context must be UTF-8") from exc
    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError("data lifecycle context is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("data lifecycle context must be a JSON object")
    return payload


def _keys(
    payload: dict[str, Any],
    *,
    allowed: set[str],
    required: set[str],
    name: str,
) -> None:
    """Reject missing or unsupported fields for one strict JSON object."""
    extra = set(payload) - allowed
    missing = required - set(payload)
    if extra:
        raise ValueError(f"{name} contains unsupported fields: {sorted(extra)!r}")
    if missing:
        raise ValueError(f"{name} is missing required fields: {sorted(missing)!r}")


def _string(value: Any, name: str) -> str:
    """Return one non-empty string without scalar coercion."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _optional_string(value: Any, name: str) -> str | None:
    """Return an optional non-empty string without coercion."""
    if value is None:
        return None
    return _string(value, name)


def _boolean(value: Any, name: str) -> bool:
    """Return one strict JSON boolean."""
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def _timestamp(value: Any, name: str) -> datetime:
    """Parse one timezone-aware ISO timestamp."""
    text = _string(value, name)
    try:
        when = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be an ISO timestamp") from exc
    if when.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return when


def _optional_timestamp(value: Any, name: str) -> str | None:
    """Validate one optional timezone-aware timestamp while preserving its text."""
    if value is None:
        return None
    text = _string(value, name)
    when = _timestamp(text, name)
    return when.astimezone(UTC).isoformat()


def _strings(value: Any, name: str) -> tuple[str, ...]:
    """Return one strict tuple of strings."""
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{name} must be an array of strings")
    return tuple(value)


def _policy(payload: Any) -> DataLifecyclePolicy:
    """Parse one full lifecycle policy without relying on dataclass defaults."""
    if not isinstance(payload, dict):
        raise ValueError("policy must be an object")
    allowed = {
        "policy_id",
        "purpose",
        "max_retention_days",
        "storage_max_sensitivity",
        "telemetry_max_sensitivity",
        "disclosure_max_sensitivity",
        "encryption_at_rest_required",
        "tls_required",
    }
    _keys(payload, allowed=allowed, required=allowed, name="policy")
    max_retention_raw = payload["max_retention_days"]
    if max_retention_raw is not None and type(max_retention_raw) is not int:
        raise ValueError("max_retention_days must be an integer or null")
    return DataLifecyclePolicy(
        policy_id=_string(payload["policy_id"], "policy_id"),
        purpose=_string(payload["purpose"], "purpose"),
        max_retention_days=max_retention_raw,
        storage_max_sensitivity=_string(
            payload["storage_max_sensitivity"], "storage_max_sensitivity"
        ),
        telemetry_max_sensitivity=_string(
            payload["telemetry_max_sensitivity"], "telemetry_max_sensitivity"
        ),
        disclosure_max_sensitivity=_string(
            payload["disclosure_max_sensitivity"], "disclosure_max_sensitivity"
        ),
        encryption_at_rest_required=_boolean(
            payload["encryption_at_rest_required"], "encryption_at_rest_required"
        ),
        tls_required=_boolean(payload["tls_required"], "tls_required"),
    )


def _decision(payload: Any) -> DataLifecycleDecision:
    """Parse one strict serialized lifecycle decision."""
    if not isinstance(payload, dict):
        raise ValueError("recorded decision must be an object")
    allowed = {
        "object_id",
        "sensitivity",
        "policy_id",
        "retain_until",
        "expired",
        "storage_allowed",
        "telemetry_allowed",
        "disclosure_allowed",
        "deletion_allowed",
        "reasons",
    }
    _keys(payload, allowed=allowed, required=allowed, name="recorded decision")
    sensitivity = _string(payload["sensitivity"], "decision sensitivity")
    if sensitivity not in SENSITIVITY_ORDER:
        raise ValueError("decision sensitivity is unsupported")
    return DataLifecycleDecision(
        object_id=_string(payload["object_id"], "decision object_id"),
        sensitivity=sensitivity,
        policy_id=_string(payload["policy_id"], "decision policy_id"),
        retain_until=_optional_timestamp(
            payload["retain_until"], "decision retain_until"
        ),
        expired=_boolean(payload["expired"], "decision expired"),
        storage_allowed=_boolean(
            payload["storage_allowed"], "decision storage_allowed"
        ),
        telemetry_allowed=_boolean(
            payload["telemetry_allowed"], "decision telemetry_allowed"
        ),
        disclosure_allowed=_boolean(
            payload["disclosure_allowed"], "decision disclosure_allowed"
        ),
        deletion_allowed=_boolean(
            payload["deletion_allowed"], "decision deletion_allowed"
        ),
        reasons=_strings(payload["reasons"], "decision reasons"),
    )


def _recorded_decision(payload: Any) -> RecordedDataLifecycleDecision | None:
    """Parse one optional recorded decision and its evaluation timestamp."""
    if payload is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError("recorded_decision must be an object or null")
    allowed = {"evaluated_at", "decision"}
    _keys(payload, allowed=allowed, required=allowed, name="recorded_decision")
    return RecordedDataLifecycleDecision(
        evaluated_at=_timestamp(payload["evaluated_at"], "recorded evaluated_at"),
        decision=_decision(payload["decision"]),
    )


def _verify_recorded_decision(context: DataLifecycleContext) -> None:
    """Require a persisted decision to equal deterministic lifecycle replay."""
    recorded = context.recorded_decision
    if recorded is None:
        return
    expected = assess_data_lifecycle(
        context.object_id,
        sensitivity=context.sensitivity,
        created_at=context.created_at,
        policy=context.policy,
        now=recorded.evaluated_at,
        legal_hold=context.legal_hold,
    )
    if recorded.decision != expected:
        raise ValueError("recorded lifecycle decision does not match policy replay")


def load_data_lifecycle_context(path: Path, *, max_bytes: int) -> DataLifecycleContext:
    """Load one strict lifecycle context and replay-verify any recorded decision."""
    payload = _read_object(path, max_bytes=max_bytes)
    allowed = {
        "schema_version",
        "object_kind",
        "object_id",
        "sensitivity",
        "created_at",
        "legal_hold",
        "policy",
        "recorded_decision",
    }
    _keys(payload, allowed=allowed, required=allowed, name="data lifecycle context")
    if payload["schema_version"] != DATA_LIFECYCLE_CONTEXT_SCHEMA_VERSION:
        raise ValueError("unsupported data lifecycle context schema version")
    object_kind = _string(payload["object_kind"], "object_kind")
    if object_kind not in _DATA_LIFECYCLE_OBJECT_KINDS:
        raise ValueError("unsupported data lifecycle object kind")
    object_id = _string(payload["object_id"], "object_id")
    if object_kind == "workspace-export" and (
        not object_id.startswith("export:") or not object_id[7:].strip()
    ):
        raise ValueError("workspace-export object_id must use export:<id>")
    sensitivity = _string(payload["sensitivity"], "sensitivity")
    if sensitivity not in SENSITIVITY_ORDER:
        raise ValueError("unsupported lifecycle sensitivity")
    context = DataLifecycleContext(
        object_kind=object_kind,
        object_id=object_id,
        sensitivity=sensitivity,
        created_at=_timestamp(payload["created_at"], "created_at"),
        legal_hold=_boolean(payload["legal_hold"], "legal_hold"),
        policy=_policy(payload["policy"]),
        recorded_decision=_recorded_decision(payload["recorded_decision"]),
    )
    _verify_recorded_decision(context)
    return context


def _same_instant(left: datetime, right: datetime) -> bool:
    """Return whether two timezone-aware timestamps identify the same instant."""
    return left.astimezone(UTC) == right.astimezone(UTC)


def resolve_data_lifecycle_context(
    context: DataLifecycleContext,
    workspace: StateWakeWorkspace,
    *,
    evaluated_at: datetime,
) -> ResolvedDataLifecycleContext:
    """Bind lifecycle policy context to durable workspace retention/deletion state."""
    if not workspace.read_only:
        raise ValueError(
            "data lifecycle investigation requires read-only workspace access"
        )
    if evaluated_at.tzinfo is None:
        raise ValueError("evaluated_at must be timezone-aware")

    original_digest: str | None
    durable_created_at: datetime
    if context.object_kind == "workspace-record":
        records, _ = workspace.repository.query_records(
            WorkspaceRecordQuery(record_id=context.object_id, limit=1)
        )
        if not records:
            raise ValueError("workspace lifecycle object does not exist")
        record = records[0]
        durable_created_at = record.created_at
        original_digest = record.artifact_digest
        if record.sensitivity != context.sensitivity:
            raise ValueError(
                "lifecycle context sensitivity disagrees with workspace record"
            )
    else:
        export_id = context.object_id.removeprefix("export:")
        export = workspace.repository.get_export(export_id)
        if export is None:
            raise ValueError("workspace lifecycle export does not exist")
        durable_created_at = _timestamp(
            export.created_at, "workspace export created_at"
        )
        original_digest = export.output_digest

    if not _same_instant(context.created_at, durable_created_at):
        raise ValueError(
            "lifecycle context creation time disagrees with workspace state"
        )

    retention = workspace.repository.get_retention(context.object_id)
    if retention is None:
        raise ValueError("workspace lifecycle retention metadata is not recorded")
    if retention.policy_id != context.policy.policy_id:
        raise ValueError("lifecycle policy identity disagrees with workspace retention")
    if retention.sensitivity != context.sensitivity:
        raise ValueError("lifecycle sensitivity disagrees with workspace retention")
    if retention.legal_hold is not context.legal_hold:
        raise ValueError("legal-hold state disagrees with workspace retention")

    current = assess_data_lifecycle(
        context.object_id,
        sensitivity=context.sensitivity,
        created_at=context.created_at,
        policy=context.policy,
        now=evaluated_at,
        legal_hold=context.legal_hold,
    )
    if retention.retain_until != current.retain_until:
        raise ValueError(
            "retention deadline disagrees with configured lifecycle policy"
        )

    deletion = workspace.repository.get_deletion(context.object_id)
    if deletion is not None:
        if deletion.object_id != context.object_id:
            raise ValueError("deletion tombstone object identity mismatch")
        if deletion.policy_id != context.policy.policy_id:
            raise ValueError("deletion tombstone policy mismatch")
        if deletion.sensitivity != context.sensitivity:
            raise ValueError("deletion tombstone sensitivity mismatch")
        if original_digest is None or deletion.digest != original_digest:
            raise ValueError(
                "deletion tombstone digest does not bind the original object"
            )
        deleted_at = _timestamp(deletion.deleted_at, "deletion deleted_at")
        if retention.retain_until is not None:
            retain_until = _timestamp(retention.retain_until, "retention retain_until")
            if deleted_at.astimezone(UTC) < retain_until.astimezone(UTC):
                raise ValueError("deletion tombstone predates retention eligibility")

    return ResolvedDataLifecycleContext(
        context=context,
        retention=retention,
        deletion=deletion,
        original_digest=original_digest,
        current_decision=current,
    )


__all__ = [
    "DATA_LIFECYCLE_CONTEXT_SCHEMA_VERSION",
    "DataLifecycleContext",
    "RecordedDataLifecycleDecision",
    "ResolvedDataLifecycleContext",
    "load_data_lifecycle_context",
    "resolve_data_lifecycle_context",
]
