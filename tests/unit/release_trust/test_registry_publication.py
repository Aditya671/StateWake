"""Canonical registry publication receipt and reconciliation regressions."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest

from statewake.release_trust import (
    ArtifactDigest,
    PublicationExecutionPermit,
    ReleasePublicationBasis,
    load_registry_publication_receipt,
    reconcile_registry_publication,
    verify_registry_publication_receipt,
    write_registry_publication_receipt,
)
from statewake.utils.json_support import JsonValue

WHEEL = b"wheel-bytes"
SDIST = b"sdist-bytes"


def _basis() -> ReleasePublicationBasis:
    return ReleasePublicationBasis(
        distribution="statewake-ai",
        version="0.4.1",
        target_repository="pypi",
        source_revision="deadbeef",
        source_tree_sha256="a" * 64,
        verification_evidence_kind="release-candidate-evidence",
        verification_evidence_sha256="b" * 64,
        artifacts=(
            ArtifactDigest(
                "statewake_ai-0.4.1-py3-none-any.whl",
                sha256(WHEEL).hexdigest(),
                len(WHEEL),
                "application/zip",
            ),
            ArtifactDigest(
                "statewake_ai-0.4.1.tar.gz",
                sha256(SDIST).hexdigest(),
                len(SDIST),
                "application/gzip",
            ),
        ),
    )


def _permit(basis: ReleasePublicationBasis) -> PublicationExecutionPermit:
    return PublicationExecutionPermit(
        basis_digest=basis.digest,
        target_repository=basis.target_repository,
        source_revision=basis.source_revision,
        artifact_sha256=tuple((item.name, item.sha256) for item in basis.artifacts),
        authorization_receipt_ids=("c" * 64,),
        authorization_receipt_digests=("d" * 64,),
        issued_at=datetime(2026, 10, 4, 12, 0, tzinfo=UTC),
    )


def _payload(basis: ReleasePublicationBasis) -> dict[str, JsonValue]:
    by_name = {item.name: item for item in basis.artifacts}
    return cast(
        dict[str, JsonValue],
        {
            "info": {"name": "statewake-ai", "version": "0.4.1"},
            "urls": [
                {
                    "filename": "statewake_ai-0.4.1-py3-none-any.whl",
                    "digests": {
                        "sha256": by_name["statewake_ai-0.4.1-py3-none-any.whl"].sha256
                    },
                    "size": len(WHEEL),
                    "url": "https://files.pythonhosted.org/packages/statewake.whl",
                    "packagetype": "bdist_wheel",
                    "upload_time_iso_8601": "2026-10-04T12:01:00+00:00",
                    "yanked": False,
                },
                {
                    "filename": "statewake_ai-0.4.1.tar.gz",
                    "digests": {"sha256": by_name["statewake_ai-0.4.1.tar.gz"].sha256},
                    "size": len(SDIST),
                    "url": "https://files.pythonhosted.org/packages/statewake.tar.gz",
                    "packagetype": "sdist",
                    "upload_time_iso_8601": "2026-10-04T12:01:01+00:00",
                    "yanked": False,
                },
            ],
        },
    )


def _bytes() -> dict[str, bytes]:
    return {
        "statewake_ai-0.4.1-py3-none-any.whl": WHEEL,
        "statewake_ai-0.4.1.tar.gz": SDIST,
    }


def test_registry_receipt_requires_exact_metadata_and_public_bytes(
    tmp_path: Path,
) -> None:
    basis = _basis()
    permit = _permit(basis)
    receipt = reconcile_registry_publication(
        basis,
        permit,
        _payload(basis),
        _bytes(),
        observed_at=datetime(2026, 10, 4, 12, 2, tzinfo=UTC),
    )
    assert receipt.basis_digest == basis.digest
    assert receipt.permit_digest == permit.digest
    assert receipt.to_dict()["release_published"] is True
    assert receipt.to_dict()["public_bytes_verified"] is True
    verify_registry_publication_receipt(receipt, basis, permit)

    path = tmp_path / "registry-receipt.json"
    write_registry_publication_receipt(receipt, path)
    loaded = load_registry_publication_receipt(path)
    assert loaded == receipt
    assert loaded.digest == receipt.digest


def test_registry_metadata_mismatch_fails_closed() -> None:
    basis = _basis()
    permit = _permit(basis)
    payload = _payload(basis)
    urls = payload["urls"]
    assert isinstance(urls, list)
    first = urls[0]
    assert isinstance(first, dict)
    first["size"] = len(WHEEL) + 1
    with pytest.raises(ValueError, match="metadata does not match"):
        reconcile_registry_publication(basis, permit, payload, _bytes())


def test_registry_public_byte_mismatch_fails_closed() -> None:
    basis = _basis()
    with pytest.raises(ValueError, match="public registry bytes do not match"):
        reconcile_registry_publication(
            basis,
            _permit(basis),
            _payload(basis),
            {**_bytes(), "statewake_ai-0.4.1.tar.gz": b"tampered"},
        )


def test_extra_or_yanked_registry_artifact_fails_closed() -> None:
    basis = _basis()
    permit = _permit(basis)
    payload = _payload(basis)
    urls = payload["urls"]
    assert isinstance(urls, list)
    urls.append(
        {
            "filename": "unexpected.whl",
            "digests": {"sha256": "e" * 64},
            "size": 1,
            "url": "https://files.pythonhosted.org/packages/unexpected.whl",
            "packagetype": "bdist_wheel",
            "yanked": False,
        }
    )
    with pytest.raises(ValueError, match="artifact set"):
        reconcile_registry_publication(basis, permit, payload, _bytes())

    payload = _payload(basis)
    urls = payload["urls"]
    assert isinstance(urls, list)
    second = urls[1]
    assert isinstance(second, dict)
    second["yanked"] = True
    with pytest.raises(ValueError, match="yanked"):
        reconcile_registry_publication(basis, permit, payload, _bytes())


def test_receipt_cannot_be_rebound_to_changed_permit_or_basis() -> None:
    basis = _basis()
    permit = _permit(basis)
    receipt = reconcile_registry_publication(basis, permit, _payload(basis), _bytes())
    changed_permit = replace(
        permit,
        authorization_receipt_ids=("e" * 64,),
        authorization_receipt_digests=("f" * 64,),
    )
    with pytest.raises(ValueError, match="permit digest"):
        verify_registry_publication_receipt(receipt, basis, changed_permit)

    changed_basis = replace(basis, source_revision="different")
    with pytest.raises(ValueError, match="permit is not bound"):
        verify_registry_publication_receipt(receipt, changed_basis, permit)


def test_receipt_loader_rejects_false_publication_claim(tmp_path: Path) -> None:
    basis = _basis()
    permit = _permit(basis)
    receipt = reconcile_registry_publication(basis, permit, _payload(basis), _bytes())
    path = tmp_path / "registry-receipt.json"
    write_registry_publication_receipt(receipt, path)
    raw = __import__("json").loads(path.read_text(encoding="utf-8"))
    raw["release_published"] = False
    path.write_text(__import__("json").dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="release_published=true"):
        load_registry_publication_receipt(path)
