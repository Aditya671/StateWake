"""Deterministic overview projection for canonical verification-report records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.presentation.claim_detail import ReportSourceContext

OVERVIEW_SCHEMA_VERSION = "overview.v1"
MAX_RECENT_REPORTS = 6


@dataclass(frozen=True, slots=True)
class OverviewReportRecord:
    """One canonical report with the durable source record that supplied it."""

    report: ReliabilityVerificationReport
    source: ReportSourceContext


@dataclass(frozen=True, slots=True)
class OverviewProjection:
    """A report-scoped aggregate that never becomes a reliability score."""

    records: tuple[OverviewReportRecord, ...]

    def to_dict(self) -> dict[str, object]:
        """Return the stable overview representation with explicit denominators."""
        reports = tuple(record.report for record in self.records)
        recent = sorted(
            self.records,
            key=lambda record: record.source.captured_at,
            reverse=True,
        )[:MAX_RECENT_REPORTS]
        total = len(reports)
        payload: dict[str, object] = {
            "schema_version": OVERVIEW_SCHEMA_VERSION,
            "scope": {
                "resource": "verification-report-records",
                "denominator": total,
                "deduplication_key": "workspace receipt id",
            },
            "as_of": None
            if not recent
            else max(record.source.captured_at for record in self.records),
            "metrics": {
                "reports_evaluated": total,
                "verified_reports": sum(1 for report in reports if report.verified),
                "reports_missing_evidence": sum(
                    1 for report in reports if bool(report.evidence_missing)
                ),
                "human_decisions_pending": sum(
                    1
                    for report in reports
                    if report.approval_status == "requires-human-approval"
                    or (
                        bool(report.human_decisions_required)
                        and report.approval_status != "approved"
                    )
                ),
            },
            "decisions": {
                "accept": sum(1 for report in reports if report.decision == "accept"),
                "review": sum(1 for report in reports if report.decision == "review"),
                "reject": sum(1 for report in reports if report.decision == "reject"),
                "other": sum(
                    1
                    for report in reports
                    if report.decision not in {"accept", "review", "reject"}
                ),
            },
            "recent_reports": [
                {
                    "record_id": record.source.record_id,
                    "claim": record.report.claim,
                    "decision": record.report.decision,
                    "verified": record.report.verified,
                    "approval_status": record.report.approval_status,
                    "candidate": {
                        "id": record.report.candidate_identity,
                        "digest": record.report.candidate_digest,
                    },
                    "profile": {
                        "id": record.report.profile_id,
                        "version": record.report.profile_version,
                    },
                    "captured_at": record.source.captured_at,
                    "report_digest": record.report.digest,
                }
                for record in recent
            ],
            "limitations": [
                "Counts describe canonical verification-report records in the configured workspace, not unique systems or production reliability.",
                "Verified report count reflects each report's recorded verified field; it does not authorize release or side effects.",
                "Human-decision pending is derived only from recorded human-decision and approval-status fields.",
            ],
        }
        return payload

    @property
    def digest(self) -> str:
        """Return a deterministic digest for conditional overview reads."""
        raw = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


def build_overview(
    records: tuple[OverviewReportRecord, ...],
) -> OverviewProjection:
    """Build the deterministic verification-report overview projection."""
    return OverviewProjection(records=records)


__all__ = [
    "MAX_RECENT_REPORTS",
    "OVERVIEW_SCHEMA_VERSION",
    "OverviewProjection",
    "OverviewReportRecord",
    "build_overview",
]
