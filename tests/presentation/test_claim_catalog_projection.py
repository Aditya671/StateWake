from __future__ import annotations

from typing import cast

from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.presentation.claim_catalog import (
    ClaimCatalogQuery,
    ClaimCatalogRecord,
    build_claim_catalog,
)
from statewake.presentation.claim_detail import ReportSourceContext


def _report(*, claim: str, decision: str = "review") -> ReliabilityVerificationReport:
    return ReliabilityVerificationReport(
        format_version="1",
        claim=claim,
        decision=decision,
        profile_id="rag_answer_verified.v1",
        profile_version="1",
        verified=False,
        evidence_included=("run",),
        evidence_omitted=(),
        checks_passed=(),
        checks_failed=(),
        source_identities=("run-1",),
        rationale=("bounded",),
        caveats=(),
        recovery_status="not-applicable",
        verifier_version="statewake-test",
        generated_at="2026-09-29T00:00:00+00:00",
        candidate_identity="candidate-1",
        candidate_digest="a" * 64,
        evidence_missing=("retrieval",),
        approval_status="requires-human-approval",
    )


def _record(record_id: str, claim: str, captured_at: str) -> ClaimCatalogRecord:
    return ClaimCatalogRecord(
        report=_report(claim=claim),
        source=ReportSourceContext(
            record_id=record_id,
            artifact_digest="b" * 64,
            producer_id="statewake.test",
            producer_type="statewake-verification-report",
            captured_at=captured_at,
        ),
    )


def test_catalog_sort_is_newest_then_record_identity_ascending() -> None:
    records = (
        _record("b" * 64, "same-time-b", "2026-09-29T00:00:00+00:00"),
        _record("c" * 64, "newest", "2026-09-29T01:00:00+00:00"),
        _record("a" * 64, "same-time-a", "2026-09-29T00:00:00+00:00"),
    )
    projection = build_claim_catalog(
        records,
        ClaimCatalogQuery(limit=10),
        scanned_receipts=3,
    ).to_dict()
    raw_items = projection["items"]
    assert isinstance(raw_items, list)
    items = cast(list[dict[str, object]], raw_items)
    assert [item["record_id"] for item in items] == [
        "c" * 64,
        "a" * 64,
        "b" * 64,
    ]


def test_catalog_text_search_is_case_insensitive_and_bounded_to_identity_fields() -> (
    None
):
    records = (
        _record("a" * 64, "Alpha Policy Decision", "2026-09-29T00:00:00+00:00"),
        _record("b" * 64, "Other Claim", "2026-09-28T00:00:00+00:00"),
    )
    payload = build_claim_catalog(
        records,
        ClaimCatalogQuery(text="ALPHA", limit=10),
        scanned_receipts=2,
    ).to_dict()
    raw_scope = payload["scope"]
    raw_items = payload["items"]
    assert isinstance(raw_scope, dict)
    assert isinstance(raw_items, list)
    scope = cast(dict[str, object], raw_scope)
    items = cast(list[dict[str, object]], raw_items)
    assert scope["matched_reports"] == 1
    assert items[0]["record_id"] == "a" * 64


def test_catalog_orders_timezone_offsets_by_actual_instant() -> None:
    records = (
        _record("a" * 64, "later-local-but-earlier-utc", "2026-09-29T01:00:00+02:00"),
        _record("b" * 64, "later-utc", "2026-09-29T00:30:00+00:00"),
    )
    payload = build_claim_catalog(
        records, ClaimCatalogQuery(limit=10), scanned_receipts=2
    ).to_dict()
    raw_items = payload["items"]
    assert isinstance(raw_items, list)
    items = cast(list[dict[str, object]], raw_items)
    assert [item["record_id"] for item in items] == [
        "b" * 64,
        "a" * 64,
    ]


def test_catalog_query_rejects_unbounded_direct_use() -> None:
    import pytest

    with pytest.raises(ValueError, match="limit"):
        ClaimCatalogQuery(limit=201)
    with pytest.raises(ValueError, match="search limit"):
        ClaimCatalogQuery(text="x" * 201)
    with pytest.raises(ValueError, match="timezone-aware"):
        build_claim_catalog(
            (_record("a" * 64, "claim", "2026-09-29T00:00:00"),),
            ClaimCatalogQuery(limit=10),
            scanned_receipts=1,
        )
