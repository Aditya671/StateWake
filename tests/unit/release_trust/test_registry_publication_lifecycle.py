"""Canonical registry publication lifecycle regressions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import cast

import pytest

from statewake.release_trust import (
    ArtifactDigest,
    PublicationExecutionPermit,
    RegistryPublicationLifecycleObservation,
    RegistryPublicationLifecycleStore,
    RegistryPublicationReceipt,
    RegistryPublishedArtifact,
    ReleasePublicationBasis,
    reconcile_registry_publication_lifecycle,
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


def _receipt(
    basis: ReleasePublicationBasis, permit: PublicationExecutionPermit
) -> RegistryPublicationReceipt:
    return RegistryPublicationReceipt(
        basis_digest=basis.digest,
        permit_digest=permit.digest,
        target_repository=basis.target_repository,
        distribution=basis.distribution,
        version=basis.version,
        registry_api_url="https://pypi.org/pypi/statewake-ai/0.4.1/json",
        observed_at=datetime(2026, 10, 4, 12, 1, tzinfo=UTC),
        artifacts=tuple(
            RegistryPublishedArtifact(
                name=item.name,
                sha256=item.sha256,
                size_bytes=item.size_bytes,
                url=f"https://files.pythonhosted.org/packages/{item.name}",
                package_type=("bdist_wheel" if item.name.endswith(".whl") else "sdist"),
                upload_time=datetime(2026, 10, 4, 12, 0, 30, tzinfo=UTC),
                yanked=False,
            )
            for item in basis.artifacts
        ),
    )


def _payload(
    basis: ReleasePublicationBasis,
    *,
    yanked: bool = False,
    reason: str | None = None,
    names: set[str] | None = None,
) -> dict[str, JsonValue]:
    urls: list[dict[str, JsonValue]] = []
    for item in basis.artifacts:
        if names is not None and item.name not in names:
            continue
        entry: dict[str, JsonValue] = {
            "filename": item.name,
            "digests": {"sha256": item.sha256},
            "size": item.size_bytes,
            "url": f"https://files.pythonhosted.org/packages/{item.name}",
            "packagetype": "bdist_wheel" if item.name.endswith(".whl") else "sdist",
            "upload_time_iso_8601": "2026-10-04T12:00:30+00:00",
            "yanked": yanked,
        }
        if reason is not None:
            entry["yanked_reason"] = reason
        urls.append(entry)
    return cast(
        dict[str, JsonValue],
        {"info": {"name": "statewake-ai", "version": "0.4.1"}, "urls": urls},
    )


def _bytes(names: set[str] | None = None) -> dict[str, bytes]:
    all_bytes = {
        "statewake_ai-0.4.1-py3-none-any.whl": WHEEL,
        "statewake_ai-0.4.1.tar.gz": SDIST,
    }
    return (
        all_bytes
        if names is None
        else {k: v for k, v in all_bytes.items() if k in names}
    )


def test_registry_lifecycle_records_yank_and_unyank_without_mutating_receipt() -> None:
    basis = _basis()
    permit = _permit(basis)
    receipt = _receipt(basis, permit)
    available = reconcile_registry_publication_lifecycle(
        receipt,
        basis,
        permit,
        _payload(basis),
        _bytes(),
        observed_at=receipt.observed_at + timedelta(minutes=1),
    )
    assert available.status == "available"
    assert available.predecessor_digest == receipt.digest
    assert available.public_bytes_verified is True

    yanked = reconcile_registry_publication_lifecycle(
        receipt,
        basis,
        permit,
        _payload(basis, yanked=True, reason="critical compatibility regression"),
        _bytes(),
        previous=available,
        observed_at=available.observed_at + timedelta(minutes=1),
    )
    assert yanked.status == "yanked"
    assert yanked.predecessor_digest == available.digest
    assert {item.yanked_reason for item in yanked.artifacts} == {
        "critical compatibility regression"
    }
    assert yanked.to_dict()["default_install_eligible"] is False

    unyanked = reconcile_registry_publication_lifecycle(
        receipt,
        basis,
        permit,
        _payload(basis),
        _bytes(),
        previous=yanked,
        observed_at=yanked.observed_at + timedelta(minutes=1),
    )
    assert unyanked.status == "available"
    assert unyanked.predecessor_digest == yanked.digest
    assert receipt.to_dict()["release_published"] is True


def test_registry_lifecycle_records_partial_file_availability_without_inferring_cause() -> (
    None
):
    basis = _basis()
    permit = _permit(basis)
    receipt = _receipt(basis, permit)
    remaining = {"statewake_ai-0.4.1-py3-none-any.whl"}
    partial = reconcile_registry_publication_lifecycle(
        receipt,
        basis,
        permit,
        _payload(basis, names=remaining),
        _bytes(remaining),
        observed_at=receipt.observed_at + timedelta(minutes=1),
    )
    assert partial.status == "partially_available"
    assert partial.missing_artifacts == ("statewake_ai-0.4.1.tar.gz",)
    assert partial.public_bytes_verified is False
    assert partial.to_dict()["registry_entry_present"] is True
    assert partial.to_dict()["default_install_eligible"] is False
    assert "does not prove deletion intent" in " ".join(
        cast(list[str], partial.to_dict()["limitations"])
    )


def test_registry_lifecycle_records_release_with_all_files_removed_as_partial() -> None:
    basis = _basis()
    permit = _permit(basis)
    receipt = _receipt(basis, permit)
    partial = reconcile_registry_publication_lifecycle(
        receipt,
        basis,
        permit,
        _payload(basis, names=set()),
        {},
        observed_at=receipt.observed_at + timedelta(minutes=1),
    )
    assert partial.status == "partially_available"
    assert partial.artifacts == ()
    assert partial.missing_artifacts == tuple(
        sorted(item.name for item in basis.artifacts)
    )


def test_registry_lifecycle_records_observed_unavailability_without_inferring_cause() -> (
    None
):
    basis = _basis()
    permit = _permit(basis)
    receipt = _receipt(basis, permit)
    unavailable = reconcile_registry_publication_lifecycle(
        receipt,
        basis,
        permit,
        None,
        {},
        unavailable_reason="release-specific registry API returned HTTP 404",
        observed_at=receipt.observed_at + timedelta(minutes=1),
    )
    assert unavailable.status == "unavailable"
    assert unavailable.artifacts == ()
    assert unavailable.public_bytes_verified is False
    assert unavailable.to_dict()["registry_entry_present"] is False
    assert "does not prove why" in " ".join(
        cast(list[str], unavailable.to_dict()["limitations"])
    )


def test_registry_lifecycle_rejects_partial_yank_and_tampered_bytes() -> None:
    basis = _basis()
    permit = _permit(basis)
    receipt = _receipt(basis, permit)
    payload = _payload(basis)
    urls = payload["urls"]
    assert isinstance(urls, list)
    first = urls[0]
    assert isinstance(first, dict)
    first["yanked"] = True
    first["yanked_reason"] = "only one file"
    with pytest.raises(ValueError, match="mixed yanked state"):
        reconcile_registry_publication_lifecycle(
            receipt, basis, permit, payload, _bytes()
        )

    with pytest.raises(ValueError, match="public registry bytes do not match"):
        reconcile_registry_publication_lifecycle(
            receipt,
            basis,
            permit,
            _payload(basis, yanked=True),
            {**_bytes(), "statewake_ai-0.4.1.tar.gz": b"tampered"},
        )


def test_registry_lifecycle_rejects_unauthorized_extra_artifact() -> None:
    basis = _basis()
    permit = _permit(basis)
    receipt = _receipt(basis, permit)
    payload = _payload(basis)
    urls = payload["urls"]
    assert isinstance(urls, list)
    urls.append(
        cast(
            JsonValue,
            {
                "filename": "foreign.whl",
                "digests": {"sha256": "0" * 64},
                "size": 1,
                "url": "https://files.pythonhosted.org/packages/foreign.whl",
                "packagetype": "bdist_wheel",
                "yanked": False,
            },
        )
    )
    with pytest.raises(ValueError, match="unauthorized release artifact"):
        reconcile_registry_publication_lifecycle(
            receipt, basis, permit, payload, _bytes()
        )


def test_registry_lifecycle_store_is_append_only_and_chain_verified(
    tmp_path: Path,
) -> None:
    basis = _basis()
    permit = _permit(basis)
    receipt = _receipt(basis, permit)
    store = RegistryPublicationLifecycleStore(tmp_path / "registry-lifecycle.jsonl")
    first = reconcile_registry_publication_lifecycle(
        receipt,
        basis,
        permit,
        _payload(basis),
        _bytes(),
        observed_at=receipt.observed_at + timedelta(minutes=1),
    )
    assert store.append(first, receipt, basis, permit) is True
    assert store.append(first, receipt, basis, permit) is False
    second = reconcile_registry_publication_lifecycle(
        receipt,
        basis,
        permit,
        _payload(basis, yanked=True, reason="bad release"),
        _bytes(),
        previous=first,
        observed_at=first.observed_at + timedelta(minutes=1),
    )
    assert store.append(second, receipt, basis, permit) is True
    assert store.read(receipt, basis, permit) == (first, second)


def test_registry_lifecycle_store_detects_tamper(tmp_path: Path) -> None:
    basis = _basis()
    permit = _permit(basis)
    receipt = _receipt(basis, permit)
    path = tmp_path / "registry-lifecycle.jsonl"
    store = RegistryPublicationLifecycleStore(path)
    first = reconcile_registry_publication_lifecycle(
        receipt,
        basis,
        permit,
        _payload(basis),
        _bytes(),
        observed_at=receipt.observed_at + timedelta(minutes=1),
    )
    store.append(first, receipt, basis, permit)
    text = path.read_text(encoding="utf-8").replace(
        '"status":"available"', '"status":"yanked"'
    )
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        store.read(receipt, basis, permit)


def test_registry_lifecycle_from_dict_fails_closed_on_derived_flags() -> None:
    basis = _basis()
    permit = _permit(basis)
    receipt = _receipt(basis, permit)
    observation = reconcile_registry_publication_lifecycle(
        receipt,
        basis,
        permit,
        _payload(basis),
        _bytes(),
        observed_at=receipt.observed_at + timedelta(minutes=1),
    )
    raw = cast(dict[str, JsonValue], observation.to_dict())
    raw["public_bytes_verified"] = False
    with pytest.raises(ValueError, match="public_bytes_verified"):
        RegistryPublicationLifecycleObservation.from_dict(raw)
