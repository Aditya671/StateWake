"""Content checks must never confuse claimed SHA-256 with observed bytes."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from statewake.release_trust import verify_release_trust_files
from tests.unit.release_trust.test_release_trust_bundle import bundle, evidence


def test_release_content_verifier_detects_missing_and_modified_files(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "statewake_ai-0.4.0-py3-none-any.whl"
    artifact.write_bytes(b"wheel")
    sample = bundle()
    configured = replace(
        sample,
        artifacts=(
            replace(
                sample.artifacts[0],
                sha256=sha256(b"wheel").hexdigest(),
                size_bytes=5,
            ),
        ),
    )
    first = verify_release_trust_files(configured, tmp_path)
    assert first.content_complete is False
    assert "artifact:statewake_ai-0.4.0-py3-none-any.whl" in first.matched
    assert first.missing
    artifact.write_bytes(b"mutated")
    second = verify_release_trust_files(configured, tmp_path)
    assert "artifact:statewake_ai-0.4.0-py3-none-any.whl" in second.mismatched


def test_release_content_verifier_never_calls_digest_match_signature_authentic(
    tmp_path: Path,
) -> None:
    source = bundle()
    assert source.signature is not None
    report = verify_release_trust_files(source, tmp_path)
    assert any("Signature authenticity" in item for item in report.limitations)
    assert report.content_complete is False


def test_release_content_verifier_rejects_traversal(tmp_path: Path) -> None:
    source = bundle()
    updated = replace(source, sbom=evidence("sbom", digest="a" * 64))
    assert updated.sbom is not None
    updated = replace(updated, sbom=replace(updated.sbom, reference="../outside.json"))
    report = verify_release_trust_files(updated, tmp_path)
    assert "sbom:sbom.json" in report.mismatched


def test_release_content_verifier_checks_every_local_file_without_claiming_signature(
    tmp_path: Path,
) -> None:
    source = bundle()
    names = (
        source.artifacts[0].name,
        *(
            item.reference
            for item in (
                *source.tests,
                source.sbom,
                source.vulnerability_scan,
                source.provenance,
            )
            if item is not None
        ),
    )
    assert all(name is not None for name in names)
    files = {}
    for name in names:
        assert name is not None
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f"content:{name}".encode())
        files[name] = sha256(target.read_bytes()).hexdigest()
    updated = replace(
        source,
        artifacts=(
            replace(
                source.artifacts[0],
                sha256=files[source.artifacts[0].name],
                size_bytes=(tmp_path / source.artifacts[0].name).stat().st_size,
            ),
        ),
        tests=tuple(
            replace(item, digest=files[item.reference]) for item in source.tests
        ),
        sbom=replace(source.sbom, digest=files[source.sbom.reference]),
        vulnerability_scan=replace(
            source.vulnerability_scan, digest=files[source.vulnerability_scan.reference]
        ),
        provenance=replace(
            source.provenance, digest=files[source.provenance.reference]
        ),
    )
    result = verify_release_trust_files(updated, tmp_path)
    assert result.content_complete is True
    assert len(result.matched) == len(names)
    assert any("Signature authenticity" in note for note in result.limitations)
