"""Regression tests for Phase 6 release-trust evidence bundles."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from statewake.release_trust import (
    ArtifactDigest,
    BuildProvenance,
    ExternalEvidence,
    HumanReleaseDecision,
    ReleaseTrustBundle,
    SourceIdentity,
    evaluate_release_trust_bundle,
    load_release_trust_bundle,
    release_claim_chain_from_bundle,
    release_trust_evidence_reference,
    verify_release_trust_bundle,
    write_release_trust_bundle,
)

D = "a" * 64
E = "b" * 64
F = "c" * 64
G = "d" * 64
H = "e" * 64
DIGEST_I = "f" * 64


def evidence(
    evidence_type: str,
    *,
    digest: str = E,
    status: str = "present",
    limitation: str | None = None,
) -> ExternalEvidence:
    return ExternalEvidence(
        evidence_type=evidence_type,
        name=f"{evidence_type}.json",
        digest=digest,
        status=status,
        reference=f"release-trust/{evidence_type}.json",
        limitation=limitation,
    )


def bundle(**changes: object) -> ReleaseTrustBundle:
    signature_limitation = "Signing is unavailable in this development environment."
    values: dict[str, object] = {
        "schema_version": "1",
        "source": SourceIdentity(
            distribution="statewake-ai",
            version="0.4.0",
            source_revision="tree:example",
            source_tree_sha256=D,
            dependency_lock_sha256=E,
        ),
        "artifacts": (
            ArtifactDigest(
                name="statewake_ai-0.4.0-py3-none-any.whl",
                sha256=F,
                size_bytes=1234,
                media_type="application/zip",
            ),
        ),
        "build": BuildProvenance(
            builder="uv_build",
            build_type="wheel",
            build_steps=("python -m compileall", "uv build"),
            environment={"python": "3.13", "platform": "test"},
        ),
        "tests": (evidence("tests", digest=G, status="passed"),),
        "sbom": evidence("sbom", digest=H),
        "vulnerability_scan": evidence(
            "vulnerability-scan", digest=DIGEST_I, status="passed"
        ),
        "signature": evidence(
            "signature",
            digest=D,
            status="limitation",
            limitation=signature_limitation,
        ),
        "provenance": evidence("build-provenance", digest=E),
        "human_decision": HumanReleaseDecision(
            actor_ref="release-owner",
            role="release approver",
            decision="pending",
        ),
        "limitations": (signature_limitation,),
    }
    values.update(changes)
    return ReleaseTrustBundle(**values)  # type: ignore[arg-type]


def test_release_trust_bundle_requires_artifact_digest() -> None:
    with pytest.raises(ValueError, match="artifact.sha256"):
        ArtifactDigest(name="dist.whl", sha256="not-a-digest", size_bytes=10)


def test_release_trust_bundle_requires_lock_status() -> None:
    with pytest.raises(ValueError, match="dependency_lock_sha256"):
        SourceIdentity(
            distribution="statewake-ai",
            version="0.4.0",
            source_revision="tree:example",
            source_tree_sha256=D,
            dependency_lock_sha256="missing",
        )


def test_unsigned_release_records_limitation_not_pass() -> None:
    item = bundle()
    notes = verify_release_trust_bundle(item)
    assert "signature-limitation-recorded" in notes
    assert item.signature is not None
    assert item.signature.status == "limitation"
    assert item.human_decision.decision == "pending"


def test_false_signature_pass_claim_is_rejected() -> None:
    with pytest.raises(ValueError, match="signature evidence must be present"):
        bundle(signature=evidence("signature", digest=D, status="passed"))


def test_slsa_provenance_reference_is_preserved_as_external_evidence() -> None:
    item = bundle()
    assert item.provenance is not None
    assert item.provenance.reference == "release-trust/build-provenance.json"
    assert item.provenance.evidence_type == "build-provenance"


def test_sbom_digest_mismatch_rejects_loaded_release_claim(tmp_path: Path) -> None:
    path = tmp_path / "release-trust.json"
    write_release_trust_bundle(bundle(), path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["sbom"]["digest"] = "0" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        load_release_trust_bundle(path)


def test_release_decision_requires_human_approval_basis() -> None:
    with pytest.raises(ValueError, match="basis digest"):
        bundle(
            human_decision=HumanReleaseDecision(
                actor_ref="release-owner",
                role="release approver",
                decision="approved",
            )
        )


def test_release_profile_consumes_release_trust_bundle() -> None:
    item = bundle()
    result = evaluate_release_trust_bundle(item)
    assert result.profile_id == "release_evidence_complete.v1"
    assert result.satisfied is False
    assert result.decision == "accepted_with_limitations"
    assert "ai-contract:human_approval" in result.failed_conditions


def test_release_profile_accepts_approved_release_trust_bundle() -> None:
    item = bundle(
        human_decision=HumanReleaseDecision(
            actor_ref="release-owner",
            role="release approver",
            decision="approved",
            basis_digest=F,
        )
    )
    result = evaluate_release_trust_bundle(item)
    assert result.satisfied is True
    assert result.decision == "accepted"


def test_release_bundle_verifies_after_json_round_trip(tmp_path: Path) -> None:
    original = bundle()
    path = tmp_path / "release-trust.json"
    write_release_trust_bundle(original, path)
    loaded = load_release_trust_bundle(path)
    assert loaded == original
    assert release_trust_evidence_reference(loaded).digest == original.digest
    chain = release_claim_chain_from_bundle(loaded)
    assert any(ref.kind == "release-trust" for ref in chain.evidence)
