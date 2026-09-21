"""Regression tests for the Tier 5 workspace query surface."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from statewake.adapters.content_store import ContentAddressedArtifactStore
from statewake.adapters.evidence_ingestion import JsonEvidenceReceiptStore
from statewake.domain.evidence_receipt import ExternalEvidenceReceipt
from statewake.workspace import (
    StateWakeWorkspace,
    WorkspaceError,
    WorkspaceRecord,
    WorkspaceRecordQuery,
)

BASE_TIME = datetime(2026, 1, 1, 12, tzinfo=UTC)


def _receipt(
    workspace: StateWakeWorkspace, suffix: str, captured_at: datetime
) -> ExternalEvidenceReceipt:
    artifact_store = ContentAddressedArtifactStore(workspace.root / "artifacts")
    receipt_store = JsonEvidenceReceiptStore(workspace.root / "receipts")
    content = suffix.encode("utf-8")
    digest = artifact_store.put(content)
    receipt = ExternalEvidenceReceipt(
        producer_type="test",
        producer_id=f"producer-{suffix}",
        artifact_digest=digest,
        artifact_size=len(content),
        captured_at=captured_at,
        source_ref=f"source-{suffix}",
        source_event_id=f"event-{suffix}",
        run_id=f"run-{suffix}",
        metadata={"case": suffix},
    )
    receipt_store.put(receipt)
    return receipt


def _index(
    workspace: StateWakeWorkspace,
    suffix: str,
    captured_at: datetime,
    *,
    sensitivity: str = "internal",
    verification_status: str | None = None,
    reliability_state: str | None = None,
) -> WorkspaceRecord:
    receipt = _receipt(workspace, suffix, captured_at)
    record = WorkspaceRecord(
        record_id=receipt.receipt_id,
        receipt=receipt,
        created_at=captured_at,
        sensitivity=sensitivity,
        policy_id="default",
        verification_status=verification_status,
        reliability_state=reliability_state,
    )
    workspace.repository.index_record(record)
    return record


def test_record_lookup_and_filters_are_typed_and_deterministic(tmp_path: Path) -> None:
    """Query the operational index without reading raw persistence manually."""
    workspace = StateWakeWorkspace.open(tmp_path / "workspace")
    first = _index(workspace, "first", BASE_TIME)
    second = _index(workspace, "second", BASE_TIME + timedelta(hours=1))

    assert workspace.get_record(first.record_id) == first
    result = workspace.query(
        WorkspaceRecordQuery(producer_id="producer-second", limit=10)
    )
    assert [record.record_id for record in result.records] == [second.record_id]

    ordered = workspace.query(WorkspaceRecordQuery(limit=10))
    assert [record.record_id for record in ordered.records] == [
        second.record_id,
        first.record_id,
    ]


def test_ingestion_with_run_id_is_queryable(tmp_path: Path) -> None:
    """Bind an observed run during ingestion so run queries remain usable."""
    workspace = StateWakeWorkspace.open(tmp_path / "workspace")
    record = workspace.ingest(
        b"run-aware",
        producer_type="test",
        producer_id="producer-run-aware",
        source_ref="source-run-aware",
        source_event_id="event-run-aware",
        run_id="run-aware",
        captured_at=BASE_TIME,
    )

    assert workspace.query_run("run-aware", limit=10).records == (record,)
    assert workspace.query_event("event-run-aware", limit=10).records == (record,)


def test_run_event_and_date_range_queries(tmp_path: Path) -> None:
    """Support run, source-event, and half-open captured-time queries."""
    workspace = StateWakeWorkspace.open(tmp_path / "workspace")
    first = _index(workspace, "first", BASE_TIME)
    second = _index(workspace, "second", BASE_TIME + timedelta(hours=1))
    third = _index(workspace, "third", BASE_TIME + timedelta(hours=2))

    assert workspace.query_run("run-second", limit=10).records == (second,)
    assert workspace.query_event("event-third", limit=10).records == (third,)
    result = workspace.query(
        WorkspaceRecordQuery(
            captured_from=BASE_TIME + timedelta(minutes=30),
            captured_to=BASE_TIME + timedelta(hours=2),
            limit=10,
        )
    )
    assert result.records == (second,)
    assert first not in result.records


def test_verification_and_reliability_filters_and_pagination(tmp_path: Path) -> None:
    """Apply state filters and bounded offset pagination over deterministic order."""
    workspace = StateWakeWorkspace.open(tmp_path / "workspace")
    records = [
        _index(
            workspace,
            f"item-{index}",
            BASE_TIME + timedelta(minutes=index),
            verification_status="verified" if index == 0 else None,
            reliability_state="trusted" if index == 0 else None,
        )
        for index in range(4)
    ]

    filtered = workspace.query(
        WorkspaceRecordQuery(
            verification_status="verified",
            reliability_state="trusted",
            limit=10,
        )
    )
    assert filtered.records == (records[0],)

    page_one = workspace.query(WorkspaceRecordQuery(limit=2, offset=0))
    page_two = workspace.query(WorkspaceRecordQuery(limit=2, offset=2))
    assert page_one.total_count == 4
    assert page_one.has_more is True
    assert page_one.next_offset == 2
    assert page_two.has_more is False
    assert page_two.next_offset is None
    assert page_one.records + page_two.records == tuple(reversed(records))


def test_sensitivity_ceiling_and_query_bounds(tmp_path: Path) -> None:
    """Respect existing StateWake sensitivity ordering and query safety bounds."""
    workspace = StateWakeWorkspace.open(tmp_path / "workspace")
    internal = _index(workspace, "internal", BASE_TIME, sensitivity="internal")
    confidential = _index(
        workspace,
        "confidential",
        BASE_TIME + timedelta(hours=1),
        sensitivity="confidential",
    )
    restricted = _index(
        workspace,
        "restricted",
        BASE_TIME + timedelta(hours=2),
        sensitivity="restricted",
    )

    result = workspace.query(WorkspaceRecordQuery(max_sensitivity="internal", limit=10))
    assert result.records == (internal,)
    result = workspace.query(
        WorkspaceRecordQuery(max_sensitivity="confidential", limit=10)
    )
    assert result.records == (confidential, internal)
    assert restricted not in result.records

    with pytest.raises(ValueError, match="limit must be between"):
        WorkspaceRecordQuery(limit=0)
    with pytest.raises(ValueError, match="limit must be between"):
        WorkspaceRecordQuery(limit=1001)
    with pytest.raises(ValueError, match="unsupported sensitivity"):
        workspace.query(WorkspaceRecordQuery(max_sensitivity="secret", limit=1))


def test_query_requires_open_workspace(tmp_path: Path) -> None:
    """Reject historical queries after the workspace handle has been closed."""
    workspace = StateWakeWorkspace.open(tmp_path / "workspace")
    workspace.close()

    with pytest.raises(WorkspaceError, match="workspace is closed"):
        workspace.query(WorkspaceRecordQuery(limit=1))
