"""Application services for deterministic behavioral comparison."""

from pathlib import Path

from ..adapters.jsonl_store import JsonlEventStore
from ..domain.diff import (
    BehavioralDiff,
    compare,
)
from ..services.evidence_service import load_manifest
from ..services.state_service import load_state


def compare_artifacts(
    before_state_path: Path,
    after_state_path: Path,
    *,
    before_evidence_path: Path | None = None,
    after_evidence_path: Path | None = None,
    before_events_path: Path | None = None,
    before_run_id: str | None = None,
    after_events_path: Path | None = None,
    after_run_id: str | None = None,
) -> BehavioralDiff:
    """Compare two state snapshots and optionally their evidence and runs."""
    before_state = load_state(before_state_path)
    after_state = load_state(after_state_path)
    before_evidence = (
        load_manifest(before_evidence_path) if before_evidence_path else None
    )
    after_evidence = load_manifest(after_evidence_path) if after_evidence_path else None
    before_events = (
        tuple(JsonlEventStore(before_events_path).validate_run(before_run_id))
        if before_events_path and before_run_id
        else None
    )
    after_events = (
        tuple(JsonlEventStore(after_events_path).validate_run(after_run_id))
        if after_events_path and after_run_id
        else None
    )
    return compare(
        before_state,
        after_state,
        before_evidence=before_evidence,
        after_evidence=after_evidence,
        before_events=before_events,
        after_events=after_events,
    )
