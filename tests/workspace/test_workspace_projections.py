"""Regression tests for the Tier 6 dataset projection surface."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from statewake.workspace import (
    DATASET_PROJECTION_SCHEMA_VERSION,
    DatasetProjection,
    NormalizedRecordProjection,
    StateWakeWorkspace,
    WorkspaceRecordQuery,
)

BASE_TIME = datetime(2026, 1, 1, 12, tzinfo=UTC)


def test_query_projection_is_structured_and_preserves_nulls(tmp_path: Path) -> None:
    """Project a logical query with stable fields and explicit null values."""
    workspace = StateWakeWorkspace.open(tmp_path / "workspace")
    record = workspace.ingest(
        b"projection",
        producer_type="test",
        producer_id="producer",
        source_ref="source",
        captured_at=BASE_TIME,
    )

    projection = workspace.project(WorkspaceRecordQuery(limit=10))

    assert projection.schema_version == DATASET_PROJECTION_SCHEMA_VERSION == "1"
    assert len(projection.records) == 1
    projected = projection.records[0]
    assert projected == NormalizedRecordProjection.from_record(record)
    payload = projected.to_dict()
    assert payload["producer_version"] is None
    assert payload["source_event_id"] is None
    assert payload["run_id"] is None
    assert payload["captured_at"] == "2026-01-01T12:00:00+00:00"
    assert payload["created_at"] == "2026-01-01T12:00:00+00:00"


def test_dataset_projection_has_stable_top_level_shape(tmp_path: Path) -> None:
    """Keep all analytical projection collections present even when empty."""
    workspace = StateWakeWorkspace.open(tmp_path / "workspace")
    page = workspace.query(WorkspaceRecordQuery(limit=10))

    projection = DatasetProjection.from_query_page(page)

    assert list(projection.to_dict()) == [
        "schema_version",
        "records",
        "relationships",
        "runs",
        "state_transitions",
        "retention",
        "deletions",
    ]
    assert projection.to_dict()["records"] == []
    assert projection.to_dict()["relationships"] == []
    assert projection.to_dict()["runs"] == []
    assert projection.to_dict()["state_transitions"] == []
    assert projection.to_dict()["retention"] == []
    assert projection.to_dict()["deletions"] == []


def test_secondary_projection_models_use_explicit_null_and_datetime_semantics() -> None:
    """Serialize all secondary projection models with stable nullable values."""
    from statewake.workspace import (
        DeletionProjection,
        RelationshipProjection,
        RetentionProjection,
        RunProjection,
        StateTransitionProjection,
    )

    relationship = RelationshipProjection("source", "target", "derived-from", BASE_TIME)
    run = RunProjection(
        "run-1", "producer", "test", None, BASE_TIME, None, "observed", None
    )
    transition = StateTransitionProjection(
        "transition-1",
        "subject",
        None,
        "trusted",
        None,
        "digest",
        BASE_TIME,
    )
    retention = RetentionProjection("object", "default", "internal", None, False)
    deletion = DeletionProjection(
        "object",
        "digest",
        "internal",
        BASE_TIME,
        "default",
        "policy-expired",
    )

    assert relationship.to_dict()["created_at"] == "2026-01-01T12:00:00+00:00"
    assert run.to_dict()["finished_at"] is None
    assert run.to_dict()["metadata"] is None
    assert transition.to_dict()["from_state"] is None
    assert transition.to_dict()["previous_digest"] is None
    assert retention.to_dict()["retain_until"] is None
    assert deletion.to_dict()["deleted_at"] == "2026-01-01T12:00:00+00:00"
