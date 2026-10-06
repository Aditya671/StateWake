"""Canonical release-publication authorization and execution boundary regressions."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from statewake.adapters.human_approval import WorkspaceHumanApprovalStore
from statewake.release_trust import (
    ArtifactDigest,
    ReleasePublicationBasis,
    issue_publication_execution_permit,
    publication_basis_from_release_trust,
    record_publication_authorization,
    resolve_publication_authorization,
    revoke_publication_authorization,
    verify_publication_artifacts,
)
from tests.unit.release_trust.test_release_trust_bundle import bundle


def _basis(tmp_path: Path) -> tuple[ReleasePublicationBasis, Path]:
    artifact = tmp_path / "dist" / "statewake_ai-0.4.1-py3-none-any.whl"
    artifact.parent.mkdir()
    artifact.write_bytes(b"wheel")
    basis = ReleasePublicationBasis(
        distribution="statewake-ai",
        version="0.4.1",
        target_repository="pypi",
        source_revision="commit:abc123",
        source_tree_sha256="a" * 64,
        verification_evidence_kind="release-candidate-evidence",
        verification_evidence_sha256="b" * 64,
        artifacts=(
            ArtifactDigest(
                name=artifact.name,
                sha256=sha256(b"wheel").hexdigest(),
                size_bytes=5,
                media_type="application/zip",
            ),
        ),
    )
    return basis, artifact.parent


def _authorize(store: WorkspaceHumanApprovalStore, basis: ReleasePublicationBasis):
    return record_publication_authorization(
        store,
        basis,
        actor_identity_ref="release-owner",
        actor_role="release-approver",
        producer_id="github-actions:openai/statewake",
        run_id="github-run:123:1",
        reason="Approve exact verified distributions for production publication.",
        idempotency_key="release-published:123",
    )[0]


def test_release_publication_basis_binds_target_and_release_bundle() -> None:
    sample = bundle()
    basis = publication_basis_from_release_trust(sample, target_repository="testpypi")
    assert basis.release_bundle_digest == sample.digest
    assert basis.verification_evidence_sha256 == sample.digest
    assert basis.target_repository == "testpypi"
    assert (
        basis.digest
        != publication_basis_from_release_trust(sample, target_repository="pypi").digest
    )


def test_execution_requires_active_exact_authority_and_exact_artifacts(
    tmp_path: Path,
) -> None:
    basis, root = _basis(tmp_path)
    store = WorkspaceHumanApprovalStore(tmp_path / "approval")
    with pytest.raises(PermissionError, match="no active"):
        issue_publication_execution_permit(
            store,
            basis,
            artifact_root=root,
            expected_producer_id="github-actions:openai/statewake",
        )
    approval = _authorize(store, basis)
    state = resolve_publication_authorization(
        store, basis, expected_producer_id="github-actions:openai/statewake"
    )
    assert state.publication_authorized
    permit = issue_publication_execution_permit(
        store,
        basis,
        artifact_root=root,
        expected_producer_id="github-actions:openai/statewake",
        now=datetime(2026, 10, 4, tzinfo=UTC),
    )
    assert permit.authorization_receipt_ids == (approval.receipt.receipt_id,)
    assert permit.to_dict()["publication_authorized"] is True
    assert permit.to_dict()["release_published"] is False


def test_revocation_invalidates_fresh_execution_without_erasing_history(
    tmp_path: Path,
) -> None:
    basis, root = _basis(tmp_path)
    store = WorkspaceHumanApprovalStore(tmp_path / "approval")
    approval = _authorize(store, basis)
    revocation, created = revoke_publication_authorization(
        store,
        basis,
        target_approval_receipt_id=approval.receipt.receipt_id,
        actor_identity_ref="release-owner",
        actor_role="release-approver",
        producer_id="github-actions:openai/statewake",
        run_id="github-run:123:1",
        reason="Release withdrawn before publication.",
        idempotency_key="release-revoked:123",
    )
    assert created
    assert revocation.contract.target_approval_receipt_id == approval.receipt.receipt_id
    state = resolve_publication_authorization(
        store, basis, expected_producer_id="github-actions:openai/statewake"
    )
    assert not state.publication_authorized
    assert state.lifecycle[0].status == "revoked"
    with pytest.raises(PermissionError, match="no active"):
        issue_publication_execution_permit(
            store,
            basis,
            artifact_root=root,
            expected_producer_id="github-actions:openai/statewake",
        )


def test_supersession_keeps_only_replacement_effective(tmp_path: Path) -> None:
    basis, _root = _basis(tmp_path)
    store = WorkspaceHumanApprovalStore(tmp_path / "approval")
    first = _authorize(store, basis)
    replacement, created = record_publication_authorization(
        store,
        basis,
        actor_identity_ref="release-owner",
        actor_role="release-approver",
        producer_id="github-actions:openai/statewake",
        run_id="github-run:124:1",
        reason="Updated approval after review correction.",
        idempotency_key="release-published:124",
        supersedes_approval_receipt_id=first.receipt.receipt_id,
    )
    assert created
    state = resolve_publication_authorization(
        store, basis, expected_producer_id="github-actions:openai/statewake"
    )
    assert [item.status for item in state.lifecycle] == ["superseded", "active"]
    assert state.active[0].receipt.receipt_id == replacement.receipt.receipt_id


def test_changed_or_extra_distribution_bytes_fail_closed(tmp_path: Path) -> None:
    basis, root = _basis(tmp_path)
    (root / basis.artifacts[0].name).write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed after authorization"):
        verify_publication_artifacts(basis, root)
    (root / basis.artifacts[0].name).write_bytes(b"wheel")
    (root / "unexpected.txt").write_text("extra", encoding="utf-8")
    with pytest.raises(ValueError, match="does not match"):
        verify_publication_artifacts(basis, root)


def test_verification_evidence_is_rechecked_at_execution(tmp_path: Path) -> None:
    basis, root = _basis(tmp_path)
    evidence = tmp_path / "release-candidate-evidence.json"
    evidence.write_bytes(b"candidate evidence")
    basis = replace(
        basis,
        verification_evidence_sha256=sha256(evidence.read_bytes()).hexdigest(),
    )
    store = WorkspaceHumanApprovalStore(tmp_path / "approval")
    _authorize(store, basis)
    issue_publication_execution_permit(
        store,
        basis,
        artifact_root=root,
        expected_producer_id="github-actions:openai/statewake",
        verification_evidence_path=evidence,
    )
    evidence.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="verification evidence changed"):
        issue_publication_execution_permit(
            store,
            basis,
            artifact_root=root,
            expected_producer_id="github-actions:openai/statewake",
            verification_evidence_path=evidence,
        )
