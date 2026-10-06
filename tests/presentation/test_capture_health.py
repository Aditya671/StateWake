"""Regression tests for read-only native capture failure-journal projections."""

from __future__ import annotations

from typing import cast

from statewake.integrations.native_capture import (
    NativeCaptureFailureJournalSnapshot,
    NativeCaptureFailureRecord,
)
from statewake.presentation.capture_health import (
    CaptureFailureQuery,
    build_capture_health,
)


def _mapping(value: object) -> dict[str, object]:
    """Narrow one JSON-like projection object for type-safe assertions."""
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _snapshot() -> NativeCaptureFailureJournalSnapshot:
    return NativeCaptureFailureJournalSnapshot(
        (
            NativeCaptureFailureRecord(
                0, "langchain.retriever_start", "AttributeError"
            ),
            NativeCaptureFailureRecord(1, "native_capture.persist", "OSError"),
            NativeCaptureFailureRecord(2, "native_capture.persist", "OSError"),
        ),
        180,
        True,
    )


def test_capture_health_keeps_recorded_failure_separate_from_success_inference() -> (
    None
):
    projection = build_capture_health(
        _snapshot(), CaptureFailureQuery(), read_limit_bytes=1024
    ).to_dict()
    assert projection["observations"] == {
        "recorded_failure_count": 3,
        "distinct_stage_count": 2,
        "distinct_error_type_count": 2,
        "status": "failures-recorded",
        "capture_success_inferred": False,
        "workspace_durability_inferred": False,
        "timestamps_available": False,
    }
    aggregates = _mapping(projection["aggregates"])
    assert aggregates["by_stage"] == [
        {"stage": "langchain.retriever_start", "count": 1},
        {"stage": "native_capture.persist", "count": 2},
    ]


def test_capture_health_filters_and_paginates_without_changing_sequence() -> None:
    projection = build_capture_health(
        _snapshot(),
        CaptureFailureQuery(stage="native_capture.persist", limit=1, offset=1),
        read_limit_bytes=1024,
    ).to_dict()
    assert projection["page"] == {
        "limit": 1,
        "offset": 1,
        "returned": 1,
        "matched": 2,
        "has_more": False,
        "next_offset": None,
    }
    assert projection["items"] == [
        {"sequence": 2, "stage": "native_capture.persist", "error_type": "OSError"}
    ]


def test_capture_health_declared_capacity_is_operator_context_not_runtime_inference() -> (
    None
):
    projection = build_capture_health(
        _snapshot(),
        CaptureFailureQuery(),
        read_limit_bytes=1024,
        declared_journal_capacity_bytes=200,
    ).to_dict()
    source = _mapping(projection["source"])
    observations = _mapping(projection["observations"])
    assert source["declared_capacity_state"] == "within-declared-capacity"
    assert source["declared_capacity_remaining_bytes"] == 20
    assert observations["workspace_durability_inferred"] is False


def test_capture_health_empty_journal_is_not_reported_as_healthy() -> None:
    snapshot = NativeCaptureFailureJournalSnapshot((), 0, False)
    projection = build_capture_health(
        snapshot, CaptureFailureQuery(), read_limit_bytes=1024
    ).to_dict()
    observations = _mapping(projection["observations"])
    source = _mapping(projection["source"])
    assert observations["status"] == "no-failures-recorded"
    assert observations["capture_success_inferred"] is False
    assert source["journal_exists"] is False
