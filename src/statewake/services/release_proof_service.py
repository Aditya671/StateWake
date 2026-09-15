"""Opinionated release-proof workflow over existing StateWake authorities."""

from __future__ import annotations

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
import json
from datetime import UTC, datetime
from pathlib import Path

from ..domain.operations import OperationalBundle
from ..domain.reliability_evidence import ReliabilityEvidenceChain
from ..domain.reliability_verification_report import ReliabilityVerificationReport
from ..services.persistence import atomic_write_text
from ..services.reliability_claim_profile_service import (
    ClaimProfileEvaluation,
    ReliabilityClaimProfile,
    evaluate_claim_profile,
    get_builtin_claim_profile,
    load_claim_profile,
)
from ..services.reliability_evidence_service import (
    load_reliability_evidence_chain,
    verify_reliability_evidence_chain,
)
from ..services.reliability_proof_bundle_service import build_reliability_proof_bundle


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
        else get_builtin_claim_profile("release-evidence-complete")
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
        checks_passed=tuple(evaluation.passed_conditions) + verification.checks,
        checks_failed=tuple(evaluation.failed_conditions) + verification.failures,
        source_identities=_source_identities(chain),
        rationale=chain.decision_rationale,
        caveats=(
            "Verification establishes integrity and binding of supplied evidence; it does not establish external correctness of the AI system.",
        ),
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
    atomic_write_text(
        path, json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
    )
    atomic_write_text(path.with_suffix(".md"), render_verification_report(report))


def render_verification_report(report: ReliabilityVerificationReport) -> str:
    """Render a human-readable verification report."""
    status = "VERIFIED" if report.verified else "NOT VERIFIED"
    lines = [
        "# Reliability Verification Report",
        "",
        f"**Status:** {status}",
        f"**Claim:** {report.claim}",
        f"**Decision:** `{report.decision}`",
        f"**Profile:** `{report.profile_id}@{report.profile_version}`",
        "",
        "## Evidence",
        "",
    ]
    lines += [f"- Included: `{item}`" for item in report.evidence_included]
    lines += [
        f"- Required but omitted: `{item}`"
        for item in report.evidence_omitted
        if item not in report.evidence_included
    ]
    lines += ["", "## Verification", ""]
    lines += [f"- PASS: `{item}`" for item in report.checks_passed]
    lines += [f"- FAIL: `{item}`" for item in report.checks_failed]
    lines += ["", "## Decision rationale", ""] + [
        f"- {item}" for item in report.rationale
    ]
    lines += [
        "",
        "## Recovery",
        "",
        f"`{report.recovery_status}`",
        "",
        "## Caveats",
        "",
    ] + [f"- {item}" for item in report.caveats]
    lines += [
        "",
        f"Verifier: `{report.verifier_version}`  ",
        f"Generated: `{report.generated_at}`  ",
        f"Report digest: `{report.digest}`",
        "",
    ]
    return "\n".join(lines)
