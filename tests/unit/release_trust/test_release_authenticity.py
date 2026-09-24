"""Authenticate a pinned signer only after independently checking release files."""

from __future__ import annotations

import json
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import pytest

from statewake.release_trust import (
    ExternalEvidence,
    ReleaseTrustBundle,
    assess_authenticated_release,
    release_signature_payload,
    verify_release_authenticity,
)
from tests.unit.release_trust.test_release_trust_bundle import bundle


def _configured_release(root: Path) -> ReleaseTrustBundle:
    initial = bundle()
    assert initial.signature is not None
    signature_file = root / "release-trust/signature.json"
    signature_file.parent.mkdir(parents=True)
    signature_file.write_text(
        json.dumps({"key_id": "trusted", "signature_hex": "00" * 64})
    )
    file_content = {initial.artifacts[0].name: b"wheel"}
    for item in (
        *initial.tests,
        initial.sbom,
        initial.vulnerability_scan,
        initial.provenance,
    ):
        assert item is not None and item.reference is not None
        file_content[item.reference] = ("contents:" + item.name).encode()
    for name, contents in file_content.items():
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(contents)

    def updated(item: ExternalEvidence | None) -> ExternalEvidence:
        assert item is not None and item.reference is not None
        return replace(item, digest=sha256(file_content[item.reference]).hexdigest())

    return replace(
        initial,
        artifacts=(
            replace(
                initial.artifacts[0], sha256=sha256(b"wheel").hexdigest(), size_bytes=5
            ),
        ),
        tests=tuple(updated(item) for item in initial.tests),
        sbom=updated(initial.sbom),
        vulnerability_scan=updated(initial.vulnerability_scan),
        provenance=updated(initial.provenance),
        signature=replace(
            initial.signature,
            status="present",
            limitation=None,
            digest=sha256(signature_file.read_bytes()).hexdigest(),
        ),
        limitations=(),
    )


def test_no_trusted_signer_never_authenticates(tmp_path: Path) -> None:
    sample = _configured_release(tmp_path)
    with pytest.raises(ValueError, match="independently trusted"):
        verify_release_authenticity(sample, tmp_path, trusted_signers={})


def test_modified_file_blocks_authenticity_before_signature(tmp_path: Path) -> None:
    sample = _configured_release(tmp_path)
    (tmp_path / sample.artifacts[0].name).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="referenced content"):
        verify_release_authenticity(
            sample, tmp_path, trusted_signers={"trusted": b"k" * 32}
        )


def test_signed_payload_excludes_signature_digest_but_binds_build_and_approval() -> (
    None
):
    sample = bundle()
    assert sample.signature is not None
    altered_sig = replace(sample, signature=replace(sample.signature, digest="1" * 64))
    assert release_signature_payload(sample) == release_signature_payload(altered_sig)
    assert release_signature_payload(sample) != release_signature_payload(
        replace(sample, artifacts=(replace(sample.artifacts[0], sha256="0" * 64),))
    )


def test_actual_ed25519_signature_verification_when_dependency_available(
    tmp_path: Path,
) -> None:
    signing = pytest.importorskip("nacl.signing")
    initial = _configured_release(tmp_path)
    key = signing.SigningKey.generate()
    # The detached signature bytes do not affect signed payload (no circularity).
    signed = key.sign(release_signature_payload(initial)).signature
    assert initial.signature is not None and initial.signature.reference is not None
    signature_file = tmp_path / initial.signature.reference
    signature_file.write_text(
        json.dumps({"key_id": "trusted", "signature_hex": signed.hex()})
    )
    sample = replace(
        initial,
        signature=replace(
            initial.signature, digest=sha256(signature_file.read_bytes()).hexdigest()
        ),
    )
    report = verify_release_authenticity(
        sample, tmp_path, trusted_signers={"trusted": bytes(key.verify_key)}
    )
    assessment = assess_authenticated_release(
        sample, tmp_path, trusted_signers={"trusted": bytes(key.verify_key)}
    )
    assert assessment.signer_authenticated
    assert not assessment.publication_authorized
    assert not assessment.human_approval_authenticated
    assert report.signature_authenticated
    assert report.content.content_complete
    assert not report.human_approval_authenticated
    assert not report.ci_execution_verified
    assert not report.scan_findings_independently_verified
    with pytest.raises(ValueError, match="signature"):
        verify_release_authenticity(
            replace(sample, build=replace(sample.build, builder="attacker")),
            tmp_path,
            trusted_signers={"trusted": bytes(key.verify_key)},
        )
