"""Regression tests for data governance and lifecycle investigation."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from statewake.domain.data_lifecycle import DataLifecyclePolicy
from statewake.presentation.data_governance import DataGovernanceProjection
from statewake.services.data_lifecycle_investigation_service import (
    DATA_LIFECYCLE_CONTEXT_SCHEMA_VERSION,
    load_data_lifecycle_context,
    resolve_data_lifecycle_context,
)
from statewake.workspace import StateWakeWorkspace, WorkspaceRecordQuery
from statewake.workspace.models import WorkspaceRecord

BASE = datetime(2026, 1, 1, 12, tzinfo=UTC)


def _policy() -> DataLifecyclePolicy:
    return DataLifecyclePolicy(
        policy_id="governance-1",
        purpose="reliability-evidence-retention",
        max_retention_days=1,
        storage_max_sensitivity="restricted",
        telemetry_max_sensitivity="internal",
        disclosure_max_sensitivity="internal",
        encryption_at_rest_required=True,
        tls_required=True,
    )


def _policy_dict(policy: DataLifecyclePolicy) -> dict[str, object]:
    return {
        "policy_id": policy.policy_id,
        "purpose": policy.purpose,
        "max_retention_days": policy.max_retention_days,
        "storage_max_sensitivity": policy.storage_max_sensitivity,
        "telemetry_max_sensitivity": policy.telemetry_max_sensitivity,
        "disclosure_max_sensitivity": policy.disclosure_max_sensitivity,
        "encryption_at_rest_required": policy.encryption_at_rest_required,
        "tls_required": policy.tls_required,
    }


def _write_record_context(
    path: Path,
    *,
    record_id: str,
    sensitivity: str,
    created_at: datetime,
    policy: DataLifecyclePolicy,
    legal_hold: bool,
    recorded_at: datetime | None = None,
    recorded_decision: dict[str, object] | None = None,
) -> None:
    payload: dict[str, object] = {
        "schema_version": DATA_LIFECYCLE_CONTEXT_SCHEMA_VERSION,
        "object_kind": "workspace-record",
        "object_id": record_id,
        "sensitivity": sensitivity,
        "created_at": created_at.isoformat(),
        "legal_hold": legal_hold,
        "policy": _policy_dict(policy),
        "recorded_decision": None,
    }
    if recorded_at is not None and recorded_decision is not None:
        payload["recorded_decision"] = {
            "evaluated_at": recorded_at.isoformat(),
            "decision": recorded_decision,
        }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _workspace(
    tmp_path: Path, *, legal_hold: bool = False
) -> tuple[Path, WorkspaceRecord, DataLifecyclePolicy]:
    root = tmp_path / "workspace"
    policy = _policy()
    with StateWakeWorkspace.open(root) as workspace:
        record = workspace.ingest(
            b"governed-payload",
            producer_type="test",
            producer_id="producer",
            source_ref="source",
            captured_at=BASE,
        )
        workspace.apply_retention(
            record.record_id, policy, legal_hold=legal_hold, now=BASE
        )
    return root, record, policy


def test_lifecycle_context_replay_and_workspace_cross_check(tmp_path: Path) -> None:
    root, record, policy = _workspace(tmp_path)
    recorded_at = record.created_at + timedelta(hours=12)
    with StateWakeWorkspace.open(root) as workspace:
        recorded_decision = workspace.evaluate_lifecycle(
            record.record_id,
            policy,
            now=recorded_at,
        )
    context_path = tmp_path / "lifecycle.json"
    _write_record_context(
        context_path,
        record_id=record.record_id,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        policy=policy,
        legal_hold=False,
        recorded_at=recorded_at,
        recorded_decision=recorded_decision.to_dict(),
    )

    context = load_data_lifecycle_context(context_path, max_bytes=1_000_000)
    with StateWakeWorkspace.open_read_only(root) as workspace:
        resolved = resolve_data_lifecycle_context(
            context,
            workspace,
            evaluated_at=record.created_at + timedelta(days=2),
        )
    assert resolved.current_decision.expired
    assert resolved.current_decision.deletion_allowed
    assert resolved.retention.policy_id == policy.policy_id
    assert resolved.deletion is None


def test_recorded_decision_must_match_policy_replay(tmp_path: Path) -> None:
    root, record, policy = _workspace(tmp_path)
    del root
    evaluated_at = record.created_at + timedelta(days=2)
    bad = {
        "object_id": record.record_id,
        "sensitivity": record.sensitivity,
        "policy_id": policy.policy_id,
        "retain_until": (record.created_at + timedelta(days=1)).isoformat(),
        "expired": False,
        "storage_allowed": True,
        "telemetry_allowed": True,
        "disclosure_allowed": True,
        "deletion_allowed": False,
        "reasons": ["retention window has not expired"],
    }
    context_path = tmp_path / "tampered-decision.json"
    _write_record_context(
        context_path,
        record_id=record.record_id,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        policy=policy,
        legal_hold=False,
        recorded_at=evaluated_at,
        recorded_decision=bad,
    )
    with pytest.raises(ValueError, match="does not match policy replay"):
        load_data_lifecycle_context(context_path, max_bytes=1_000_000)


def test_workspace_retention_mismatch_fails_closed(tmp_path: Path) -> None:
    root, record, policy = _workspace(tmp_path, legal_hold=True)
    context_path = tmp_path / "mismatched-hold.json"
    _write_record_context(
        context_path,
        record_id=record.record_id,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        policy=policy,
        legal_hold=False,
    )
    context = load_data_lifecycle_context(context_path, max_bytes=1_000_000)
    with StateWakeWorkspace.open_read_only(root) as workspace:
        with pytest.raises(ValueError, match="legal-hold state disagrees"):
            resolve_data_lifecycle_context(
                context,
                workspace,
                evaluated_at=record.created_at + timedelta(days=2),
            )


def test_deletion_tombstone_binds_original_digest_without_payload(
    tmp_path: Path,
) -> None:
    root, record, policy = _workspace(tmp_path)
    with StateWakeWorkspace.open(root) as workspace:
        workspace.delete_expired(
            record.record_id,
            now=record.created_at + timedelta(days=2),
        )
    context_path = tmp_path / "deleted.json"
    _write_record_context(
        context_path,
        record_id=record.record_id,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        policy=policy,
        legal_hold=False,
    )
    context = load_data_lifecycle_context(context_path, max_bytes=1_000_000)
    with StateWakeWorkspace.open_read_only(root) as workspace:
        resolved = resolve_data_lifecycle_context(
            context,
            workspace,
            evaluated_at=record.created_at + timedelta(days=3),
        )
    assert resolved.deletion is not None
    assert resolved.deletion.digest == record.artifact_digest
    assert "content" not in resolved.deletion.to_dict()


def test_projection_keeps_policy_requirements_and_authority_boundaries(
    tmp_path: Path,
) -> None:
    root, record, policy = _workspace(tmp_path, legal_hold=True)
    context_path = tmp_path / "projection.json"
    _write_record_context(
        context_path,
        record_id=record.record_id,
        sensitivity=record.sensitivity,
        created_at=record.created_at,
        policy=policy,
        legal_hold=True,
    )
    context = load_data_lifecycle_context(context_path, max_bytes=1_000_000)
    with StateWakeWorkspace.open_read_only(root) as workspace:
        resolved = resolve_data_lifecycle_context(
            context,
            workspace,
            evaluated_at=record.created_at + timedelta(days=2),
        )
    payload = DataGovernanceProjection(resolved).to_dict()
    assert payload["schema_version"] == "data-governance-investigation.v2"
    assert payload["durable_retention"]["legal_hold"] is True  # type: ignore[index]
    assert payload["current_decision"]["expired"] is True  # type: ignore[index]
    assert payload["current_decision"]["deletion_allowed"] is False  # type: ignore[index]
    assert payload["confidentiality_requirements"] == {
        "encryption_at_rest_required": True,
        "tls_required": True,
        "host_requirement_satisfaction_evaluated": False,
    }
    assert payload["authorization"]["deletion_executed_by_this_view"] is False  # type: ignore[index]
    encoded = json.dumps(payload)
    assert str(context_path) not in encoded
    assert record.record_id not in encoded


def test_lifecycle_context_rejects_symlink_and_byte_overflow(tmp_path: Path) -> None:
    target = tmp_path / "context.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "link.json"
    link.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        load_data_lifecycle_context(link, max_bytes=100)
    with pytest.raises(OverflowError, match="byte limit"):
        load_data_lifecycle_context(target, max_bytes=1)


def test_workspace_export_context_uses_durable_export_retention(tmp_path: Path) -> None:
    root = tmp_path / "workspace-export"
    policy = _policy()
    with StateWakeWorkspace.open(root) as workspace:
        record = workspace.ingest(
            b"export-source",
            producer_type="test",
            producer_id="producer",
            source_ref="source",
            captured_at=BASE,
        )
        export_result = workspace.export_json(
            WorkspaceRecordQuery(record_id=record.record_id),
            workspace.configuration.export_root / "json" / "governed.json",
        )
        export = workspace.repository.get_export(export_result.export_id)
        assert export is not None
        created_at = datetime.fromisoformat(export.created_at)
        workspace.apply_export_retention(
            export.export_id,
            policy,
            sensitivity="internal",
            legal_hold=False,
            now=created_at,
        )
    context_path = tmp_path / "export-context.json"
    context_path.write_text(
        json.dumps(
            {
                "schema_version": DATA_LIFECYCLE_CONTEXT_SCHEMA_VERSION,
                "object_kind": "workspace-export",
                "object_id": f"export:{export.export_id}",
                "sensitivity": "internal",
                "created_at": export.created_at,
                "legal_hold": False,
                "policy": _policy_dict(policy),
                "recorded_decision": None,
            }
        ),
        encoding="utf-8",
    )
    context = load_data_lifecycle_context(context_path, max_bytes=1_000_000)
    with StateWakeWorkspace.open_read_only(root) as workspace:
        resolved = resolve_data_lifecycle_context(
            context,
            workspace,
            evaluated_at=created_at + timedelta(days=2),
        )
    assert resolved.current_decision.expired
    assert resolved.current_decision.deletion_allowed
    assert resolved.original_digest == export.output_digest
