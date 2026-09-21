"""Opinionated release-proof workflow over existing StateWake authorities."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from ..domain.operations import OperationalBundle
from ..domain.reliability_claim_profile import ReliabilityClaimProfile
from ..domain.reliability_evidence import ReliabilityEvidenceChain
from ..domain.reliability_verification_report import ReliabilityVerificationReport
from ..reports.json_report import render_json_report
from ..reports.markdown import render_markdown_report
from ..services.persistence import atomic_write_text
from ..services.reliability_claim_profile_service import (
    ClaimProfileEvaluation,
    evaluate_claim_profile,
    load_claim_profile,
)
from ..services.reliability_evidence_service import (
    load_reliability_evidence_chain,
    verify_reliability_evidence_chain,
)
from ..services.reliability_proof_bundle_service import build_reliability_proof_bundle


def _default_release_proof_profile() -> ReliabilityClaimProfile:
    """Return the legacy release-proof profile used by the existing workflow.

    The Phase 2 release profile remains available for AI release-evidence
    claims. This helper preserves the older proof-bundle workflow whose input
    chain predates AI contracts.
    """
    return ReliabilityClaimProfile(
        profile_id="release-evidence-complete",
        version="1",
        title="Release evidence complete",
        description=(
            "Legacy release-proof workflow requiring the core reliability "
            "evidence chain without requiring Phase 1 AI contracts."
        ),
        required_evidence_kinds=("run", "state", "provenance", "integrity"),
        required_verification_conditions=(
            "chain_verified",
            "reconciliation_verified",
            "decision_rationale_present",
        ),
        allowed_decisions=("accept", "review", "reject"),
        required_reconciliation_states=("verified", "recovered"),
        required_reliability_states=("reliable", "recovered"),
        caveats=("Release authorization remains a separate human decision.",),
    )


def _source_identities(chain: ReliabilityEvidenceChain) -> tuple[str, ...]:
    """Return the source identities associated with the release proof."""
    refs = (
        chain.run,
        chain.state,
        *chain.evidence,
        chain.provenance,
        chain.integrity,
        chain.reconciliation_ref,
        chain.recovery_ref,
        chain.attestation_ref,
        chain.decision_basis_ref,
        chain.comparison_ref,
        chain.reconciliation_binding_ref,
    )
    return tuple(ref.identity for ref in refs if ref is not None)


def build_release_proof(
    *,
    attestation_path: Path,
    evidence_chain_path: Path,
    history_path: Path,
    evidence_root: Path,
    output: Path,
    profile: ReliabilityClaimProfile | None = None,
    profile_path: Path | None = None,
    report_path: Path | None = None,
) -> tuple[OperationalBundle, ReliabilityVerificationReport, ClaimProfileEvaluation]:
    """Verify, apply a bounded claim profile, then emit the existing portable proof bundle."""
    if profile is not None and profile_path is not None:
        raise ValueError("profile and profile_path are mutually exclusive")
    selected = profile or (
        load_claim_profile(profile_path)
        if profile_path is not None
        else _default_release_proof_profile()
    )
    chain = load_reliability_evidence_chain(evidence_chain_path)
    verify_reliability_evidence_chain(chain, root=evidence_root)
    evaluation = evaluate_claim_profile(chain, selected)
    if not evaluation.satisfied:
        raise ValueError(
            "claim profile was not satisfied: "
            + "; ".join(evaluation.failed_conditions)
        )
    bundle, verification = build_reliability_proof_bundle(
        attestation_path=attestation_path,
        evidence_chain_path=evidence_chain_path,
        history_path=history_path,
        evidence_root=evidence_root,
        output=output,
    )
    present_kinds = set()
    for ref in (
        chain.run,
        chain.state,
        *chain.evidence,
        chain.provenance,
        chain.integrity,
        chain.reconciliation_ref,
        chain.recovery_ref,
        chain.attestation_ref,
    ):
        if ref is not None:
            present_kinds.add(ref.kind)
    evidence_omitted = tuple(
        kind for kind in selected.required_evidence_kinds if kind not in present_kinds
    )
    report = ReliabilityVerificationReport(
        format_version="1",
        claim=selected.title,
        decision=chain.decision,
        profile_id=selected.profile_id,
        profile_version=selected.version,
        verified=verification.verified and evaluation.satisfied,
        candidate_identity=chain.chain_id,
        candidate_digest=chain.digest(),
        report_type="release",
        evidence_included=tuple(
            ref.kind
            for ref in (
                chain.run,
                chain.state,
                *chain.evidence,
                chain.provenance,
                chain.integrity,
            )
            if ref is not None  # type: ignore
        ),
        evidence_omitted=evidence_omitted,
        evidence_missing=evidence_omitted,
        checks_passed=tuple(evaluation.passed_conditions) + verification.checks,
        checks_failed=tuple(evaluation.failed_conditions) + verification.failures,
        source_identities=_source_identities(chain),
        rationale=chain.decision_rationale,
        caveats=(
            "Verification establishes integrity and binding of supplied evidence; "
            "it does not establish external correctness of the AI system.",
            *evaluation.caveats,
        ),
        residual_risks=(
            "External correctness and release authorization remain outside "
            "this verification report.",
        ),
        human_decisions_required=("Human release approval",),
        allowed_use=("Use as release evidence input for human review.",),
        prohibited_use=("Do not treat this report as release approval.",),
        machine_readable_appendix=(
            "reliability_evidence_chain",
            "claim_profile_evaluation",
        ),
        artifact_digests=(chain.digest(), verification.digest),
        profile_evaluation_digest=sha256(
            json.dumps(
                evaluation.to_dict(),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        approval_status="requires-human-approval",
        recovery_status=chain.reconciliation_state,
        verifier_version="statewake-" + __import__("statewake").__version__,
        generated_at=datetime.now(UTC).isoformat(),
    )
    if report_path is not None:
        write_verification_report(report, report_path)
    return bundle, report, evaluation


def write_verification_report(
    report: ReliabilityVerificationReport, path: Path
) -> None:
    """Persist a human-readable verification report atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, render_json_report(report))
    atomic_write_text(path.with_suffix(".md"), render_verification_report(report))


def render_verification_report(report: ReliabilityVerificationReport) -> str:
    """Render a human-readable verification report."""
    return render_markdown_report(report)
