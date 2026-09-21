"""Tests for workspace-level integrity and verification reporting."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from statewake.domain.data_lifecycle import DataLifecyclePolicy
from statewake.workspace import StateWakeWorkspace, WorkspaceRecordQuery
from statewake.workspace.verification import WorkspaceVerificationReport

CAPTURED_AT = datetime(2026, 1, 1, tzinfo=UTC)


def _workspace(tmp_path: Path) -> StateWakeWorkspace:
    return StateWakeWorkspace.open(tmp_path / ".statewake")


def _record(workspace: StateWakeWorkspace):
    return workspace.ingest(
        b"verification payload",
        producer_type="test-producer",
        producer_id="producer-1",
        source_ref="source-1",
        captured_at=CAPTURED_AT,
    )


def _verified_report(workspace: StateWakeWorkspace) -> WorkspaceVerificationReport:
    """Require the workspace-wide verification result for assertions."""
    report = workspace.verify()
    assert report is not None
    return report


def test_workspace_verify_reports_healthy(tmp_path: Path) -> None:
    """A complete workspace verifies as healthy."""
    workspace = _workspace(tmp_path)
    record = _record(workspace)

    report = _verified_report(workspace)

    assert report.status == "healthy"
    assert report.healthy
    assert report.checked_records == 1
    assert report.checked_receipts == 1
    assert report.checked_artifacts == 1
    assert not report.issues
    workspace.verify(record)


def test_workspace_verify_detects_orphans_as_limitations(tmp_path: Path) -> None:
    """Unindexed payloads are reported without invalidating indexed evidence."""
    workspace = _workspace(tmp_path)
    _record(workspace)
    orphan_digest = "a" * 64
    orphan_path = (
        workspace.configuration.artifact_root / orphan_digest[:2] / orphan_digest[2:]
    )
    orphan_path.parent.mkdir(parents=True)
    orphan_path.write_bytes(b"orphan")
    orphan_receipt = workspace.configuration.receipt_root / "orphan.json"
    orphan_receipt.write_text("{}", encoding="utf-8")

    report = _verified_report(workspace)

    assert report.status == "healthy with limitations"
    assert report.orphan_artifacts == (str(orphan_path),)
    assert report.orphan_receipts == (str(orphan_receipt),)


def test_workspace_verify_reports_missing_artifact_as_incomplete(
    tmp_path: Path,
) -> None:
    """A referenced but absent artifact is incomplete rather than silently healthy."""
    workspace = _workspace(tmp_path)
    record = _record(workspace)
    artifact_path = (
        workspace.configuration.artifact_root
        / record.artifact_digest[:2]
        / record.artifact_digest[2:]
    )
    artifact_path.unlink()

    report = _verified_report(workspace)

    assert report.status == "incomplete"
    assert any(issue.code == "ARTIFACT_MISSING" for issue in report.issues)


def test_workspace_verify_reports_tampered_artifact_as_invalid(tmp_path: Path) -> None:
    """Artifact byte tampering is delegated to the canonical evidence verifier."""
    workspace = _workspace(tmp_path)
    record = _record(workspace)
    artifact_path = (
        workspace.configuration.artifact_root
        / record.artifact_digest[:2]
        / record.artifact_digest[2:]
    )
    artifact_path.write_bytes(b"tampered")

    report = _verified_report(workspace)

    assert report.status == "invalid"
    assert any(issue.code == "EVIDENCE_INVALID" for issue in report.issues)


def test_workspace_verify_reports_manifest_mismatch_as_invalid(tmp_path: Path) -> None:
    """Manifest identity drift is reported instead of silently repaired."""
    workspace = _workspace(tmp_path)
    payload = json.loads(
        workspace.configuration.manifest_path.read_text(encoding="utf-8")
    )
    payload["workspace_id"] = "different-workspace"
    workspace.configuration.manifest_path.write_text(
        json.dumps(payload), encoding="utf-8"
    )

    report = _verified_report(workspace)

    assert report.status == "invalid"
    assert any(issue.code == "MANIFEST_MISMATCH" for issue in report.issues)


def test_workspace_verify_accepts_deleted_record_with_tombstone(tmp_path: Path) -> None:
    """Expected retention deletion is distinct from an integrity failure."""
    workspace = _workspace(tmp_path)
    record = _record(workspace)
    policy = DataLifecyclePolicy(
        policy_id="short",
        purpose="workspace-test",
        max_retention_days=1,
        storage_max_sensitivity="restricted",
        disclosure_max_sensitivity="restricted",
    )
    workspace.apply_retention(record.record_id, policy, now=CAPTURED_AT)
    workspace.delete_expired(
        record.record_id,
        now=CAPTURED_AT + timedelta(days=2),
    )

    report = _verified_report(workspace)

    assert report.status == "healthy"
    assert report.checked_receipts == 1
    assert report.checked_artifacts == 0


def test_workspace_verify_detects_export_digest_drift(tmp_path: Path) -> None:
    """Export metadata remains bound to its persisted output digest."""
    workspace = _workspace(tmp_path)
    _record(workspace)
    output = workspace.configuration.export_root / "json" / "dataset.json"
    result = workspace.export_json(WorkspaceRecordQuery(limit=1), output)
    assert result.output_digest
    output.write_bytes(output.read_bytes() + b"tampered")

    report = _verified_report(workspace)

    assert report.status == "invalid"
    assert any(issue.code == "EXPORT_DIGEST_MISMATCH" for issue in report.issues)


def test_workspace_verify_rejects_artifact_symlink(tmp_path: Path) -> None:
    """Canonical artifact storage must not escape the workspace through symlinks."""
    workspace = _workspace(tmp_path)
    record = _record(workspace)
    artifact_path = (
        workspace.configuration.artifact_root
        / record.artifact_digest[:2]
        / record.artifact_digest[2:]
    )
    replacement = artifact_path.with_suffix(".external")
    replacement.write_bytes(b"external")
    artifact_path.unlink()
    try:
        artifact_path.symlink_to(replacement)
    except OSError:
        pytest.skip("symlinks are unavailable in this environment")

    report = _verified_report(workspace)

    assert report.status == "invalid"
    assert any(issue.code == "ARTIFACT_SYMLINK" for issue in report.issues)


def test_workspace_verify_detects_dangling_metadata_reference(tmp_path: Path) -> None:
    """Retention metadata pointing to an unknown object is an invalid workspace."""
    workspace = _workspace(tmp_path)
    with sqlite3.connect(workspace.configuration.database_path) as database:
        database.execute(
            "INSERT INTO retention (object_id, policy_id, sensitivity, retain_until, legal_hold) "
            "VALUES (?, ?, ?, ?, ?)",
            ("unknown", "policy", "internal", None, 0),
        )

    report = _verified_report(workspace)

    assert report.status == "invalid"
    assert any(issue.code == "DANGLING_RETENTION" for issue in report.issues)


def test_workspace_verify_reports_corrupt_repository(tmp_path: Path) -> None:
    """A repository corruption discovered after opening is classified as corrupt."""
    workspace = _workspace(tmp_path)
    workspace.configuration.database_path.write_bytes(b"not sqlite")

    report = _verified_report(workspace)

    assert report.status == "corrupt"
    assert any(issue.code == "REPOSITORY_UNAVAILABLE" for issue in report.issues)
