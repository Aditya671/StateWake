"""Pure read projections for the StateWake claim-detail human experience."""

from __future__ import annotations

from dataclasses import dataclass

from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)

SUMMARY_SCHEMA_VERSION = "claim-summary.v1"
DETAIL_SCHEMA_VERSION = "claim-detail.v1"
MAX_SUMMARY_REASONS = 8


@dataclass(frozen=True, slots=True)
class ReportSourceContext:
    """Identify the durable workspace record that supplied one report."""

    record_id: str
    artifact_digest: str
    producer_id: str
    producer_type: str
    captured_at: str
    run_id: str | None = None
    sensitivity: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return the stable source-context representation."""
        return {
            "record_id": self.record_id,
            "artifact_digest": self.artifact_digest,
            "producer_id": self.producer_id,
            "producer_type": self.producer_type,
            "captured_at": self.captured_at,
            "run_id": self.run_id,
            "sensitivity": self.sensitivity,
        }


@dataclass(frozen=True, slots=True)
class SummaryReason:
    """Represent one source-bound reason that blocks stronger verification."""

    kind: str
    source_ref: str
    text: str

    def to_dict(self) -> dict[str, str]:
        """Return the stable reason representation."""
        return {
            "kind": self.kind,
            "source_ref": self.source_ref,
            "text": self.text,
        }


@dataclass(frozen=True, slots=True)
class ClaimSummaryProjection:
    """Task-oriented deterministic summary derived from one canonical report."""

    report: ReliabilityVerificationReport
    reasons: tuple[SummaryReason, ...]

    def to_dict(self) -> dict[str, object]:
        """Return the stable UI summary representation."""
        report = self.report
        return {
            "schema_version": SUMMARY_SCHEMA_VERSION,
            "candidate": {
                "id": report.candidate_identity,
                "digest": report.candidate_digest,
            },
            "profile": {
                "id": report.profile_id,
                "version": report.profile_version,
            },
            "claim": report.claim,
            "decision": report.decision,
            "verification": {
                "verified": report.verified,
                "passed": len(report.checks_passed),
                "failed": len(report.checks_failed),
                "unrun": len(report.checks_unrun),
                "unknown": len(report.checks_unknown),
            },
            "evidence": {
                "included": len(report.evidence_included),
                "omitted": len(report.evidence_omitted),
                "missing": len(report.evidence_missing),
            },
            "reasons": [reason.to_dict() for reason in self.reasons],
            "human_decision": {
                "required": bool(report.human_decisions_required)
                or report.approval_status == "requires-human-approval",
                "approval_status": report.approval_status,
                "required_actions": list(report.human_decisions_required),
            },
            "caveats": list(report.caveats),
            "residual_risks": list(report.residual_risks),
            "report_digest": report.digest,
            "generated_at": report.generated_at,
            "as_of": None,
        }


@dataclass(frozen=True, slots=True)
class ClaimDetailProjection:
    """Read-only claim detail backed by the exact canonical report."""

    report: ReliabilityVerificationReport
    source: ReportSourceContext
    summary: ClaimSummaryProjection

    def to_dict(self) -> dict[str, object]:
        """Return the stable claim-detail representation."""
        report = self.report
        return {
            "schema_version": DETAIL_SCHEMA_VERSION,
            "source": self.source.to_dict(),
            "summary": self.summary.to_dict(),
            "checks": {
                "passed": list(report.checks_passed),
                "failed": list(report.checks_failed),
                "unrun": list(report.checks_unrun),
                "unknown": list(report.checks_unknown),
            },
            "evidence": {
                "included": list(report.evidence_included),
                "omitted": list(report.evidence_omitted),
                "missing": list(report.evidence_missing),
                "source_identities": list(report.source_identities),
                "artifact_digests": list(report.artifact_digests),
            },
            "decision_rationale": list(report.rationale),
            "recovery_status": report.recovery_status,
            "allowed_use": list(report.allowed_use),
            "prohibited_use": list(report.prohibited_use),
            "machine_readable_appendix": list(report.machine_readable_appendix),
            "profile_evaluation_digest": report.profile_evaluation_digest,
            "verifier_version": report.verifier_version,
            "generated_at": report.generated_at,
            "report_digest": report.digest,
            "links": {
                "canonical_json": f"/api/v1/reports/{self.source.record_id}",
                "canonical_markdown": (
                    f"/api/v1/reports/{self.source.record_id}/markdown"
                ),
            },
        }


def _blocking_reasons(
    report: ReliabilityVerificationReport,
) -> tuple[SummaryReason, ...]:
    """Project only recorded blocker identities without inventing explanations."""
    candidates: list[SummaryReason] = []
    candidates.extend(
        SummaryReason("failed-check", value, value) for value in report.checks_failed
    )
    candidates.extend(
        SummaryReason("missing-evidence", value, value)
        for value in report.evidence_missing
    )
    candidates.extend(
        SummaryReason("unrun-check", value, value) for value in report.checks_unrun
    )
    candidates.extend(
        SummaryReason("unknown-check", value, value) for value in report.checks_unknown
    )
    candidates.extend(
        SummaryReason("omitted-evidence", value, value)
        for value in report.evidence_omitted
    )
    return tuple(candidates[:MAX_SUMMARY_REASONS])


def build_claim_summary(
    report: ReliabilityVerificationReport,
) -> ClaimSummaryProjection:
    """Build a deterministic source-bound summary from one report."""
    return ClaimSummaryProjection(report=report, reasons=_blocking_reasons(report))


def build_claim_detail(
    report: ReliabilityVerificationReport,
    source: ReportSourceContext,
) -> ClaimDetailProjection:
    """Build a deterministic claim detail from canonical source fields only."""
    return ClaimDetailProjection(
        report=report,
        source=source,
        summary=build_claim_summary(report),
    )


__all__ = [
    "ClaimDetailProjection",
    "ClaimSummaryProjection",
    "DETAIL_SCHEMA_VERSION",
    "MAX_SUMMARY_REASONS",
    "ReportSourceContext",
    "SUMMARY_SCHEMA_VERSION",
    "SummaryReason",
    "build_claim_detail",
    "build_claim_summary",
]
