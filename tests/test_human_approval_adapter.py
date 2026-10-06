"""Regression tests for workspace-backed canonical human-approval evidence."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from statewake.adapters.human_approval import (
    ApprovalAlreadyRecordedError,
    ApprovalIdempotencyConflictError,
    WorkspaceHumanApprovalStore,
)


def _append(store: WorkspaceHumanApprovalStore, **changes: str):
    """Append one fixed approval request with optional field changes."""
    values = {
        "target_record_id": "a" * 64,
        "candidate_identity": "candidate-1",
        "candidate_digest": "b" * 64,
        "report_digest": "c" * 64,
        "profile_id": "release_evidence_complete.v1",
        "profile_version": "1",
        "actor_identity_ref": "reviewer:alice",
        "actor_role": "reliability-reviewer",
        "producer_id": "statewake.test.approver",
        "run_id": "run-1",
        "approval_action": "approve-release-evidence",
        "scope": "candidate release evidence",
        "reason": "Evidence reviewed against the exact report basis.",
        "idempotency_key": "approval-1",
    }
    values.update(changes)
    return store.append(**values)


def _store(root: Path) -> WorkspaceHumanApprovalStore:
    """Create a deterministic approval store for tests."""
    return WorkspaceHumanApprovalStore(
        root,
        now=lambda: datetime(2026, 9, 27, 12, 0, tzinfo=UTC),
    )


def test_approval_store_roundtrips_canonical_contract_and_receipt(
    tmp_path: Path,
) -> None:
    """Persist approval through existing CAS/receipt authorities and verify read-back."""
    store = _store(tmp_path / "workspace")
    record, created = _append(store)

    assert created is True
    assert record.contract.approval_basis_digest == "c" * 64
    assert record.contract.approval_action == "approve-release-evidence"
    assert record.contract.scope == "candidate release evidence"

    loaded = store.for_target("a" * 64, report_digest="c" * 64)
    assert len(loaded) == 1
    assert loaded[0].contract.to_dict() == record.contract.to_dict()
    assert loaded[0].receipt.to_dict() == record.receipt.to_dict()


def test_approval_store_is_idempotent_and_rejects_changed_reuse(tmp_path: Path) -> None:
    """Return an exact retry while rejecting changed intent under the same key."""
    store = _store(tmp_path / "workspace")
    first, created = _append(store)
    replay, replay_created = _append(store)

    assert created is True
    assert replay_created is False
    assert replay.receipt.receipt_id == first.receipt.receipt_id

    with pytest.raises(ApprovalIdempotencyConflictError):
        _append(store, reason="Changed reason")


def test_approval_store_rejects_duplicate_actor_authority_for_same_basis(
    tmp_path: Path,
) -> None:
    """Prevent a second approval record that only changes the request identity."""
    store = _store(tmp_path / "workspace")
    _append(store)

    with pytest.raises(ApprovalAlreadyRecordedError):
        _append(store, idempotency_key="approval-2", reason="Another rationale")


def test_approval_store_fails_closed_on_tampered_artifact(tmp_path: Path) -> None:
    """Reject changed approval bytes instead of displaying them as approved evidence."""
    workspace = tmp_path / "workspace"
    store = _store(workspace)
    record, _ = _append(store)
    artifact = (
        workspace
        / "artifacts"
        / record.receipt.artifact_digest[:2]
        / record.receipt.artifact_digest[2:]
    )
    artifact.write_bytes(b'{"tampered":true}\n')

    with pytest.raises(ValueError, match="Artifact integrity failure"):
        store.for_target("a" * 64, report_digest="c" * 64)


def test_concurrent_exact_approval_retries_create_one_durable_record(
    tmp_path: Path,
) -> None:
    """Serialize concurrent exact retries without duplicate approval evidence."""
    root = tmp_path / "workspace"

    def submit() -> tuple[str, bool]:
        store = _store(root)
        record, created = _append(store)
        return record.receipt.receipt_id, created

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _index: submit(), range(4)))

    assert len({receipt_id for receipt_id, _created in results}) == 1
    assert sum(1 for _receipt_id, created in results if created) == 1
    assert len(_store(root).for_target("a" * 64, report_digest="c" * 64)) == 1


def _revoke(
    store: WorkspaceHumanApprovalStore,
    target_approval_receipt_id: str,
    **changes: str,
):
    """Revoke one fixed approval with optional field changes."""
    values = {
        "target_record_id": "a" * 64,
        "target_approval_receipt_id": target_approval_receipt_id,
        "candidate_identity": "candidate-1",
        "candidate_digest": "b" * 64,
        "report_digest": "c" * 64,
        "profile_id": "release_evidence_complete.v1",
        "profile_version": "1",
        "actor_identity_ref": "reviewer:alice",
        "actor_role": "reliability-reviewer",
        "producer_id": "statewake.test.approver",
        "run_id": "run-1",
        "approval_action": "approve-release-evidence",
        "scope": "candidate release evidence",
        "reason": "Approval withdrawn after updated human review.",
        "idempotency_key": "revocation-1",
    }
    values.update(changes)
    return store.revoke(**values)


def test_approval_revocation_is_append_only_idempotent_and_removes_effective_approval(
    tmp_path: Path,
) -> None:
    """Revoke one approval without deleting history and preserve exact retry semantics."""
    store = _store(tmp_path / "workspace")
    approval, _ = _append(store)

    revocation, created = _revoke(store, approval.receipt.receipt_id)
    replay, replay_created = _revoke(store, approval.receipt.receipt_id)

    assert created is True
    assert replay_created is False
    assert replay.receipt.receipt_id == revocation.receipt.receipt_id
    lifecycle = store.lifecycle_for_target("a" * 64, report_digest="c" * 64)
    assert len(lifecycle) == 1
    assert lifecycle[0].status == "revoked"
    assert lifecycle[0].approval.receipt.receipt_id == approval.receipt.receipt_id
    assert lifecycle[0].revocation is not None
    assert lifecycle[0].revocation.receipt.receipt_id == revocation.receipt.receipt_id
    assert store.active_for_target("a" * 64, report_digest="c" * 64) == []
    assert len(store.for_target("a" * 64, report_digest="c" * 64)) == 1


def test_revoked_approval_can_be_reapproved_without_mutating_history(
    tmp_path: Path,
) -> None:
    """Allow a fresh approval after revocation while retaining the revoked predecessor."""
    store = _store(tmp_path / "workspace")
    first, _ = _append(store)
    _revoke(store, first.receipt.receipt_id)

    replacement, created = _append(
        store,
        idempotency_key="approval-2",
        reason="Approval restored after the human review concern was resolved.",
    )

    assert created is True
    lifecycle = store.lifecycle_for_target("a" * 64, report_digest="c" * 64)
    states = {item.approval.receipt.receipt_id: item.status for item in lifecycle}
    assert states[first.receipt.receipt_id] == "revoked"
    assert states[replacement.receipt.receipt_id] == "active"
    assert store.active_for_target("a" * 64, report_digest="c" * 64) == [replacement]


def test_approval_supersession_links_immutable_predecessor_and_new_active_approval(
    tmp_path: Path,
) -> None:
    """Supersede an active approval by appending a replacement canonical approval."""
    store = _store(tmp_path / "workspace")
    first, _ = _append(store)

    replacement, created = _append(
        store,
        idempotency_key="approval-2",
        reason="Updated rationale replaces the prior human approval.",
        supersedes_approval_receipt_id=first.receipt.receipt_id,
    )

    assert created is True
    assert replacement.contract.metadata is not None
    assert (
        replacement.contract.metadata["supersedes_approval_receipt_id"]
        == first.receipt.receipt_id
    )
    lifecycle = store.lifecycle_for_target("a" * 64, report_digest="c" * 64)
    items = {item.approval.receipt.receipt_id: item for item in lifecycle}
    assert items[first.receipt.receipt_id].status == "superseded"
    assert (
        items[first.receipt.receipt_id].superseded_by_receipt_id
        == replacement.receipt.receipt_id
    )
    assert items[replacement.receipt.receipt_id].status == "active"
    assert items[replacement.receipt.receipt_id].superseded_by_receipt_id is None
    assert store.active_for_target("a" * 64, report_digest="c" * 64) == [replacement]


def test_lifecycle_rejects_transition_of_inactive_or_wrong_authority_approval(
    tmp_path: Path,
) -> None:
    """Fail closed on second transitions and authority changes."""
    from statewake.adapters.human_approval import (
        ApprovalLifecycleConflictError,
        ApprovalLifecycleTargetError,
    )

    store = _store(tmp_path / "workspace")
    first, _ = _append(store)
    replacement, _ = _append(
        store,
        idempotency_key="approval-2",
        reason="Superseding approval.",
        supersedes_approval_receipt_id=first.receipt.receipt_id,
    )

    with pytest.raises(ApprovalLifecycleConflictError):
        _revoke(store, first.receipt.receipt_id, idempotency_key="revocation-2")
    with pytest.raises(ApprovalLifecycleTargetError):
        _revoke(
            store,
            replacement.receipt.receipt_id,
            producer_id="statewake.other.approver",
            idempotency_key="revocation-3",
        )


def test_approval_store_fails_closed_on_tampered_revocation_artifact(
    tmp_path: Path,
) -> None:
    """Reject changed revocation bytes instead of treating the approval as safely revoked."""
    workspace = tmp_path / "workspace"
    store = _store(workspace)
    approval, _ = _append(store)
    revocation, _ = _revoke(store, approval.receipt.receipt_id)
    artifact = (
        workspace
        / "artifacts"
        / revocation.receipt.artifact_digest[:2]
        / revocation.receipt.artifact_digest[2:]
    )
    artifact.write_bytes(b'{"tampered":true}\n')

    with pytest.raises(ValueError, match="Artifact integrity failure"):
        store.lifecycle_for_target("a" * 64, report_digest="c" * 64)
