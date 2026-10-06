"""Deterministic comparison projection for two canonical verification reports."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256

from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.presentation.claim_detail import ReportSourceContext

COMPARISON_SCHEMA_VERSION = "claim-comparison.v1"


def _delta(before: tuple[str, ...], after: tuple[str, ...]) -> dict[str, list[str]]:
    """Return stable added/removed values while preserving source order."""
    before_set = set(before)
    after_set = set(after)
    return {
        "added": [value for value in after if value not in before_set],
        "removed": [value for value in before if value not in after_set],
    }


@dataclass(frozen=True, slots=True)
class ClaimComparisonProjection:
    """Compare two reports without assigning cause, severity, or overall score."""

    left_report: ReliabilityVerificationReport
    left_source: ReportSourceContext
    right_report: ReliabilityVerificationReport
    right_source: ReportSourceContext

    @property
    def digest(self) -> str:
        """Return a deterministic digest for this read-only comparison."""
        return sha256(
            json.dumps(
                self.to_dict(),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

    def to_dict(self) -> dict[str, object]:
        """Return the stable comparison representation."""
        left = self.left_report
        right = self.right_report
        warnings: list[str] = []
        if left.profile_id != right.profile_id:
            warnings.append("profile-id-differs")
        if left.profile_version != right.profile_version:
            warnings.append("profile-version-differs")
        if left.claim != right.claim:
            warnings.append("claim-text-differs")
        if left.report_type != right.report_type:
            warnings.append("report-type-differs")
        same_scope = not warnings
        return {
            "schema_version": COMPARISON_SCHEMA_VERSION,
            "semantic_scope_same": same_scope,
            "non_equivalence_warnings": warnings,
            "left": self._side(left, self.left_source),
            "right": self._side(right, self.right_source),
            "changes": {
                "candidate_digest_changed": (
                    left.candidate_digest != right.candidate_digest
                ),
                "decision": {
                    "before": left.decision,
                    "after": right.decision,
                    "changed": left.decision != right.decision,
                },
                "verified": {
                    "before": left.verified,
                    "after": right.verified,
                    "changed": left.verified != right.verified,
                },
                "approval_status": {
                    "before": left.approval_status,
                    "after": right.approval_status,
                    "changed": left.approval_status != right.approval_status,
                },
                "checks": {
                    "passed": _delta(left.checks_passed, right.checks_passed),
                    "failed": _delta(left.checks_failed, right.checks_failed),
                    "unrun": _delta(left.checks_unrun, right.checks_unrun),
                    "unknown": _delta(left.checks_unknown, right.checks_unknown),
                },
                "evidence": {
                    "included": _delta(left.evidence_included, right.evidence_included),
                    "missing": _delta(left.evidence_missing, right.evidence_missing),
                    "omitted": _delta(left.evidence_omitted, right.evidence_omitted),
                },
                "caveats": _delta(left.caveats, right.caveats),
                "residual_risks": _delta(left.residual_risks, right.residual_risks),
                "human_decisions_required": _delta(
                    left.human_decisions_required,
                    right.human_decisions_required,
                ),
            },
            "limitations": [
                "A digest difference proves changed bytes, not the cause or severity of the change.",
                "When semantic scope differs, the two reports are shown side by side but are not treated as equivalent evaluations.",
            ],
        }

    @staticmethod
    def _side(
        report: ReliabilityVerificationReport,
        source: ReportSourceContext,
    ) -> dict[str, object]:
        """Return one source-bound side of the comparison."""
        return {
            "record_id": source.record_id,
            "report_digest": report.digest,
            "candidate": {
                "id": report.candidate_identity,
                "digest": report.candidate_digest,
            },
            "profile": {
                "id": report.profile_id,
                "version": report.profile_version,
            },
            "claim": report.claim,
            "report_type": report.report_type,
            "decision": report.decision,
            "verified": report.verified,
            "approval_status": report.approval_status,
            "generated_at": report.generated_at,
            "captured_at": source.captured_at,
        }


def build_claim_comparison(
    left_report: ReliabilityVerificationReport,
    left_source: ReportSourceContext,
    right_report: ReliabilityVerificationReport,
    right_source: ReportSourceContext,
) -> ClaimComparisonProjection:
    """Build a deterministic comparison from two already validated reports."""
    return ClaimComparisonProjection(
        left_report=left_report,
        left_source=left_source,
        right_report=right_report,
        right_source=right_source,
    )


__all__ = [
    "COMPARISON_SCHEMA_VERSION",
    "ClaimComparisonProjection",
    "build_claim_comparison",
]
