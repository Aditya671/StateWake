"""Release-script regressions for post-publication registry reconciliation."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from scripts.release import reconcile_registry_publication as reconcile_script
from statewake.release_trust import (
    ArtifactDigest,
    PublicationExecutionPermit,
    RegistryPublicationReceipt,
    RegistryPublishedArtifact,
    ReleasePublicationBasis,
    load_registry_publication_receipt,
    write_publication_execution_permit,
    write_release_publication_basis,
)


def _evidence(tmp_path: Path) -> tuple[Path, Path, RegistryPublicationReceipt]:
    artifact = ArtifactDigest(
        name="statewake_ai-0.4.1-py3-none-any.whl",
        sha256=sha256(b"wheel").hexdigest(),
        size_bytes=5,
        media_type="application/zip",
    )
    basis = ReleasePublicationBasis(
        distribution="statewake-ai",
        version="0.4.1",
        target_repository="pypi",
        source_revision="deadbeef",
        source_tree_sha256="a" * 64,
        verification_evidence_kind="release-candidate-evidence",
        verification_evidence_sha256="b" * 64,
        artifacts=(artifact,),
    )
    permit = PublicationExecutionPermit(
        basis_digest=basis.digest,
        target_repository="pypi",
        source_revision=basis.source_revision,
        artifact_sha256=((artifact.name, artifact.sha256),),
        authorization_receipt_ids=("c" * 64,),
        authorization_receipt_digests=("d" * 64,),
        issued_at=datetime(2026, 10, 4, 12, 0, tzinfo=UTC),
    )
    receipt = RegistryPublicationReceipt(
        basis_digest=basis.digest,
        permit_digest=permit.digest,
        target_repository="pypi",
        distribution=basis.distribution,
        version=basis.version,
        registry_api_url="https://pypi.org/pypi/statewake-ai/0.4.1/json",
        observed_at=datetime(2026, 10, 4, 12, 1, tzinfo=UTC),
        artifacts=(
            RegistryPublishedArtifact(
                name=artifact.name,
                sha256=artifact.sha256,
                size_bytes=artifact.size_bytes,
                url="https://files.pythonhosted.org/packages/statewake.whl",
                package_type="bdist_wheel",
                upload_time=datetime(2026, 10, 4, 12, 0, 30, tzinfo=UTC),
                yanked=False,
            ),
        ),
    )
    basis_path = tmp_path / "basis.json"
    permit_path = tmp_path / "permit.json"
    write_release_publication_basis(basis, basis_path)
    write_publication_execution_permit(permit, permit_path)
    return basis_path, permit_path, receipt


def test_reconciliation_script_writes_canonical_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    basis_path, permit_path, receipt = _evidence(tmp_path)
    output = tmp_path / "registry-receipt.json"
    monkeypatch.setattr(
        reconcile_script,
        "fetch_registry_publication",
        lambda basis, permit, timeout: receipt,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reconcile_registry_publication.py",
            "--basis",
            str(basis_path),
            "--permit",
            str(permit_path),
            "--target",
            "pypi",
            "--output",
            str(output),
            "--attempts",
            "1",
        ],
    )
    assert reconcile_script.main() == 0
    persisted = load_registry_publication_receipt(output)
    assert persisted == receipt
    assert persisted.to_dict()["release_published"] is True


def test_reconciliation_script_rejects_target_rebinding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    basis_path, permit_path, _receipt = _evidence(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reconcile_registry_publication.py",
            "--basis",
            str(basis_path),
            "--permit",
            str(permit_path),
            "--target",
            "testpypi",
            "--output",
            str(tmp_path / "receipt.json"),
        ],
    )
    with pytest.raises(PermissionError, match="target does not match"):
        reconcile_script.main()
