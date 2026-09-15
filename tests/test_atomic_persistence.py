import json
from pathlib import Path

from statewake.domain.reliability_claim_profile import ReliabilityClaimProfile
from statewake.domain.reliability_decision_basis import ReliabilityDecisionBasis
from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.services.persistence import atomic_write_text
from statewake.services.release_proof_service import write_verification_report
from statewake.services.reliability_claim_profile_service import write_claim_profile
from statewake.services.reliability_decision_basis_service import (
    write_reliability_decision_basis,
)


def _report():
    return ReliabilityVerificationReport(
        format_version="1",
        claim="Claim",
        decision="accept",
        profile_id="profile",
        profile_version="1",
        verified=True,
        evidence_included=("run",),
        evidence_omitted=(),
        checks_passed=("ok",),
        checks_failed=(),
        source_identities=("run-1",),
        rationale=("because",),
        caveats=("bounded",),
        recovery_status="verified",
        verifier_version="statewake-0.6.1",
        generated_at="2026-09-11T00:00:00+00:00",
    )


def _profile():
    return ReliabilityClaimProfile(
        profile_id="profile",
        version="1",
        title="Profile",
        required_evidence_kinds=("run",),
        required_verification_conditions=("chain_verified",),
        allowed_decisions=("accept",),
    )


def _basis():
    return ReliabilityDecisionBasis(
        format_version="1",
        basis_type="manual",
        basis_id="basis-1",
        version="1",
        decision="accept",
        reliability_state="reliable",
        rationale=("because",),
        input_digests=(),
    )


def test_atomic_text_replaces_existing_destination_without_temporary_artifact(
    tmp_path: Path,
):
    path = tmp_path / "artifact.json"
    path.write_text("old", encoding="utf-8")
    atomic_write_text(path, "new")
    assert path.read_text(encoding="utf-8") == "new"
    assert list(tmp_path.glob(".artifact.json.*.tmp")) == []


def test_domain_artifact_writers_use_atomic_persistence(tmp_path: Path):
    report_path = tmp_path / "reports" / "report.json"
    profile_path = tmp_path / "profiles" / "profile.json"
    basis_path = tmp_path / "basis" / "basis.json"
    write_verification_report(_report(), report_path)
    write_claim_profile(_profile(), profile_path)
    write_reliability_decision_basis(_basis(), basis_path)
    for path in (report_path, report_path.with_suffix(".md"), profile_path, basis_path):
        assert path.is_file()
        assert (
            json.loads(path.read_text(encoding="utf-8"))
            if path.suffix == ".json"
            else path.read_text(encoding="utf-8")
        )
    assert not list(tmp_path.rglob("*.tmp"))
