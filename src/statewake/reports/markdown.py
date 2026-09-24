"""Markdown renderer for StateWake human verification reports."""

from __future__ import annotations

from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.reports.sections import bullet_lines, safe_report_text
from statewake.reports.validation import validate_report


def render_markdown_report(report: ReliabilityVerificationReport) -> str:
    """Render a deterministic human-readable verification report."""
    validate_report(report)
    status = "VERIFIED" if report.verified else "NOT VERIFIED"
    lines = [
        "# Reliability Verification Report",
        "",
        "## Candidate identity",
        "",
        f"- Candidate: `{safe_report_text(str(report.candidate_identity))}`",
        f"- Candidate digest: `{safe_report_text(str(report.candidate_digest))}`",
        f"- Report type: `{safe_report_text(str(report.report_type))}`",
        "",
        "## Intended claim",
        "",
        f"- Claim: {safe_report_text(report.claim)}",
        f"- Profile: `{safe_report_text(str(report.profile_id))}@{safe_report_text(str(report.profile_version))}`",
        f"- Profile evaluation digest: `{report.profile_evaluation_digest or 'not-recorded'}`",
        "",
        "## Decision",
        "",
        f"- Verification status: **{status}**",
        f"- StateWake decision: `{safe_report_text(str(report.decision))}`",
        f"- Approval status: `{safe_report_text(str(report.approval_status))}`",
        "",
        "## Evidence included",
        "",
    ]
    lines += bullet_lines("Included", report.evidence_included)
    lines += ["", "## Evidence omitted", ""]
    lines += bullet_lines("Omitted", report.evidence_omitted)
    lines += ["", "## Evidence missing", ""]
    lines += bullet_lines("Missing", report.evidence_missing)
    lines += ["", "## Verification checks", ""]
    lines += bullet_lines("PASS", report.checks_passed)
    lines += bullet_lines("FAIL", report.checks_failed)
    lines += bullet_lines("UNRUN-ENV", report.checks_unrun)
    lines += bullet_lines("UNKNOWN", report.checks_unknown)
    lines += [
        "",
        "## State transitions",
        "",
        f"- Recovery status: `{safe_report_text(str(report.recovery_status))}`",
    ]
    lines += ["", "## Recovery and reconciliation", ""]
    if report.recovery_status in {"verified", "recovered"}:
        lines.append(
            "- Failure and recovery state are preserved as explicit report fields."
        )
    else:
        lines.append("- Recovery is not verified in this report.")
    lines += ["", "## Caveats", ""]
    lines += [f"- {safe_report_text(item)}" for item in report.caveats] or ["- none"]
    lines += ["", "## Residual risk", ""]
    lines += [f"- {safe_report_text(item)}" for item in report.residual_risks] or [
        "- none"
    ]
    lines += ["", "## Human decisions required", ""]
    lines += [
        f"- {safe_report_text(item)}" for item in report.human_decisions_required
    ] or ["- none"]
    lines += ["", "## Machine-readable appendix", ""]
    lines += bullet_lines("Source identity", report.source_identities)
    lines += bullet_lines("Artifact digest", report.artifact_digests)
    lines += bullet_lines("Appendix", report.machine_readable_appendix)
    lines += ["", "## Decision rationale", ""]
    lines += [f"- {safe_report_text(item)}" for item in report.rationale] or ["- none"]
    lines += [
        "",
        f"Verifier: `{safe_report_text(str(report.verifier_version))}`  ",
        f"Generated: `{safe_report_text(str(report.generated_at))}`  ",
        f"Report digest: `{safe_report_text(str(report.digest))}`",
        "",
    ]
    return "\n".join(lines)


__all__ = ["render_markdown_report"]
