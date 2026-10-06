"""Regression coverage for the portable reliability-proof investigation projection."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from zipfile import ZipFile

from statewake.presentation.proof_bundle import build_reliability_proof_investigation
from statewake.services.operations_service import verify_bundle
from statewake.services.reliability_proof_bundle_service import (
    build_reliability_proof_bundle,
    verify_reliability_proof_bundle,
)
from tests.support.reliability_proof import prepare_reliability_proof_fixture


def _build(tmp_path: Path) -> Path:
    attestation, chain, history = prepare_reliability_proof_fixture(tmp_path)
    output = tmp_path / "proof.zip"
    build_reliability_proof_bundle(
        attestation_path=attestation,
        evidence_chain_path=chain,
        history_path=history,
        evidence_root=tmp_path,
        output=output,
    )
    return output


def _mapping(value: object) -> dict[str, object]:
    """Narrow one JSON-like projection object for type-safe assertions."""
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _mapping_list(value: object) -> list[dict[str, object]]:
    """Narrow one JSON-like projection list for type-safe assertions."""
    assert isinstance(value, list)
    return cast(list[dict[str, object]], value)


def test_projection_keeps_portable_verification_and_authorization_separate(
    tmp_path: Path,
) -> None:
    path = _build(tmp_path)
    bundle = verify_bundle(path)
    report, descriptor = verify_reliability_proof_bundle(path)
    projection = build_reliability_proof_investigation(
        bundle, report, descriptor
    ).to_dict()

    assert projection["schema_version"] == "proof-bundle-investigation.v1"
    assert projection["verification"] == {
        "verified": True,
        "checks": list(report.checks),
        "failures": [],
        "offline_reverification_succeeded": True,
        "source_set_complete": True,
    }
    assert projection["authorization"] == {
        "human_approval_evaluated": False,
        "publication_authorized": False,
        "release_authorized": False,
    }
    boundary = projection["portable_dataset_boundary"]
    assert isinstance(boundary, dict)
    assert boundary["this_is_reliability_proof"] is True
    assert boundary["workspace_portable_dataset_is_distinct"] is True


def test_format_three_reports_lineage_and_completeness_as_verified(
    tmp_path: Path,
) -> None:
    path = _build(tmp_path)
    bundle = verify_bundle(path)
    report, descriptor = verify_reliability_proof_bundle(path)
    payload = build_reliability_proof_investigation(
        bundle, report, descriptor
    ).to_dict()

    assert payload["proof"]["format_version"] == "3"  # type: ignore[index]
    assert payload["lineage"]["required_by_format"] is True  # type: ignore[index]
    assert payload["lineage"]["status"] == "verified"  # type: ignore[index]
    assert payload["completeness"]["required_by_format"] is True  # type: ignore[index]
    assert payload["completeness"]["present"] is True  # type: ignore[index]
    assert payload["completeness"]["status"] == "verified"  # type: ignore[index]


def test_projection_does_not_expose_zip_member_paths_or_raw_content(
    tmp_path: Path,
) -> None:
    path = _build(tmp_path)
    bundle = verify_bundle(path)
    report, descriptor = verify_reliability_proof_bundle(path)
    payload = build_reliability_proof_investigation(
        bundle, report, descriptor
    ).to_dict()

    for artifact in _mapping_list(payload["artifacts"]):
        assert "path" not in artifact
        assert "content" not in artifact
    rendered = str(payload)
    assert str(tmp_path) not in rendered


def test_operational_verifier_rejects_tampered_packaged_bytes(tmp_path: Path) -> None:
    path = _build(tmp_path)
    tampered = tmp_path / "tampered.zip"
    with ZipFile(path) as source, ZipFile(tampered, "w") as target:
        for info in source.infolist():
            content = source.read(info.filename)
            if info.filename.endswith("proof/attestation.json"):
                content += b"\n"
            target.writestr(info, content)

    try:
        verify_bundle(tampered)
    except ValueError as exc:
        message = str(exc).lower()
        assert "digest mismatch" in message or "size mismatch" in message
    else:
        raise AssertionError("tampered proof bundle unexpectedly verified")
