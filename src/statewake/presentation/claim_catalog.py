"""Bounded read projection for discovering canonical verification reports."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.presentation.claim_detail import ReportSourceContext

CLAIM_CATALOG_SCHEMA_VERSION = "claim-catalog.v1"
MAX_CLAIM_CATALOG_PAGE_LIMIT = 200
MAX_CLAIM_CATALOG_FILTER_CHARS = 256
MAX_CLAIM_CATALOG_TEXT_CHARS = 200


@dataclass(frozen=True, slots=True)
class ClaimCatalogRecord:
    """One canonical report and the durable workspace record that supplied it."""

    report: ReliabilityVerificationReport
    source: ReportSourceContext

    def to_dict(self) -> dict[str, object]:
        """Return the stable catalog item representation."""
        report = self.report
        return {
            "record_id": self.source.record_id,
            "captured_at": self.source.captured_at,
            "run_id": self.source.run_id,
            "claim": report.claim,
            "report_type": report.report_type,
            "decision": report.decision,
            "verified": report.verified,
            "approval_status": report.approval_status,
            "candidate": {
                "id": report.candidate_identity,
                "digest": report.candidate_digest,
            },
            "profile": {
                "id": report.profile_id,
                "version": report.profile_version,
            },
            "evidence": {
                "included": len(report.evidence_included),
                "omitted": len(report.evidence_omitted),
                "missing": len(report.evidence_missing),
            },
            "checks": {
                "failed": len(report.checks_failed),
                "unrun": len(report.checks_unrun),
                "unknown": len(report.checks_unknown),
            },
            "human_decision_required": bool(report.human_decisions_required)
            or report.approval_status == "requires-human-approval",
            "report_digest": report.digest,
            "generated_at": report.generated_at,
        }


@dataclass(frozen=True, slots=True)
class ClaimCatalogQuery:
    """Allowlisted, bounded filters for the verification-report catalog."""

    decision: str | None = None
    verified: bool | None = None
    approval_status: str | None = None
    profile_id: str | None = None
    candidate_id: str | None = None
    text: str | None = None
    limit: int = 50
    offset: int = 0

    def __post_init__(self) -> None:
        """Validate the standalone projection query contract."""
        if self.verified is not None and not isinstance(self.verified, bool):
            raise ValueError("verified must be a boolean when provided")
        for field_name in (
            "decision",
            "approval_status",
            "profile_id",
            "candidate_id",
            "text",
        ):
            value = getattr(self, field_name)
            if value is not None and not value.strip():
                raise ValueError(f"{field_name} must not be blank when provided")
            if (
                value is not None
                and field_name != "text"
                and len(value) > MAX_CLAIM_CATALOG_FILTER_CHARS
            ):
                raise ValueError(f"{field_name} exceeds the catalog filter limit")
        if self.text is not None and len(self.text) > MAX_CLAIM_CATALOG_TEXT_CHARS:
            raise ValueError("text exceeds the catalog search limit")
        if self.limit < 1 or self.limit > MAX_CLAIM_CATALOG_PAGE_LIMIT:
            raise ValueError(
                f"limit must be between 1 and {MAX_CLAIM_CATALOG_PAGE_LIMIT}"
            )
        if self.offset < 0:
            raise ValueError("offset must be non-negative")

    def matches(self, record: ClaimCatalogRecord) -> bool:
        """Return whether one canonical report satisfies all configured filters."""
        report = record.report
        if self.decision is not None and report.decision != self.decision:
            return False
        if self.verified is not None and report.verified is not self.verified:
            return False
        if (
            self.approval_status is not None
            and report.approval_status != self.approval_status
        ):
            return False
        if self.profile_id is not None and report.profile_id != self.profile_id:
            return False
        if (
            self.candidate_id is not None
            and report.candidate_identity != self.candidate_id
        ):
            return False
        if self.text is not None:
            needle = self.text.casefold()
            haystacks = (
                report.claim,
                report.report_type,
                report.decision,
                report.approval_status,
                report.profile_id,
                report.candidate_identity,
            )
            if not any(needle in value.casefold() for value in haystacks):
                return False
        return True

    def to_dict(self) -> dict[str, object]:
        """Return the normalized query contract used to derive the response digest."""
        return {
            "decision": self.decision,
            "verified": self.verified,
            "approval_status": self.approval_status,
            "profile_id": self.profile_id,
            "candidate_id": self.candidate_id,
            "text": self.text,
            "limit": self.limit,
            "offset": self.offset,
        }


@dataclass(frozen=True, slots=True)
class ClaimCatalogProjection:
    """One deterministic page from a bounded canonical-report discovery scan."""

    records: tuple[ClaimCatalogRecord, ...]
    query: ClaimCatalogQuery
    scanned_receipts: int
    total_reports: int

    def to_dict(self) -> dict[str, object]:
        """Return the stable claim-catalog API representation."""
        matched = tuple(record for record in self.records if self.query.matches(record))
        start = self.query.offset
        page = matched[start : start + self.query.limit]
        next_offset = start + len(page)
        has_more = next_offset < len(matched)
        return {
            "schema_version": CLAIM_CATALOG_SCHEMA_VERSION,
            "scope": {
                "resource": "verification-report-records",
                "deduplication_key": "workspace receipt id",
                "sort": "captured_at_desc_record_id_asc",
                "scanned_receipts": self.scanned_receipts,
                "total_reports": self.total_reports,
                "matched_reports": len(matched),
            },
            "query": self.query.to_dict(),
            "page": {
                "limit": self.query.limit,
                "offset": self.query.offset,
                "returned": len(page),
                "has_more": has_more,
                "next_offset": next_offset if has_more else None,
            },
            "items": [record.to_dict() for record in page],
            "limitations": [
                "Discovery covers canonical verification-report records within the configured bounded workspace scan.",
                "Filters describe recorded report fields; they do not evaluate model correctness, release permission, or production reliability.",
                "Free-text search is a case-insensitive substring match over claim, report type, decision, approval status, profile ID, and candidate ID only.",
            ],
        }

    @property
    def digest(self) -> str:
        """Return the deterministic response digest for conditional reads."""
        raw = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


def _captured_at(record: ClaimCatalogRecord) -> datetime:
    """Return one timezone-aware capture instant for deterministic ordering."""
    value = datetime.fromisoformat(record.source.captured_at.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("catalog captured_at must be timezone-aware")
    return value


def build_claim_catalog(
    records: tuple[ClaimCatalogRecord, ...],
    query: ClaimCatalogQuery,
    *,
    scanned_receipts: int,
) -> ClaimCatalogProjection:
    """Sort canonical reports and build one bounded discovery projection."""
    by_identity = sorted(records, key=lambda record: record.source.record_id)
    ordered = tuple(
        sorted(
            by_identity,
            key=_captured_at,
            reverse=True,
        )
    )
    return ClaimCatalogProjection(
        records=ordered,
        query=query,
        scanned_receipts=scanned_receipts,
        total_reports=len(ordered),
    )


__all__ = [
    "CLAIM_CATALOG_SCHEMA_VERSION",
    "MAX_CLAIM_CATALOG_FILTER_CHARS",
    "MAX_CLAIM_CATALOG_PAGE_LIMIT",
    "MAX_CLAIM_CATALOG_TEXT_CHARS",
    "ClaimCatalogProjection",
    "ClaimCatalogQuery",
    "ClaimCatalogRecord",
    "build_claim_catalog",
]
