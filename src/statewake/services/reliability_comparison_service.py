"""Build and verify canonical behavioral-comparison evidence from existing diff authority."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from statewake.utils.json_support import load_object

from ..adapters.jsonl_store import JsonlEventStore
from ..domain.diff import (
    BehavioralDiff,
    compare,
)
from ..domain.reliability_comparison import (
    ReliabilityBehavioralComparison,
    ReliabilityComparisonInput,
)
from ..domain.reliability_evidence import EvidenceReference
from ..services.evidence_service import load_manifest
from ..services.persistence import atomic_write_text
from ..services.state_service import load_state


def _file_digest(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    return sha256(path.read_bytes()).hexdigest()


def _safe(root: Path, source: str) -> Path:
    """Return a sanitized value suitable for reconciliation diagnostics."""
    root = root.resolve()
    candidate = (root / source.replace("\\", "/")).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"comparison source escapes root: {source}")
    return candidate


def _diff_payload(diff: BehavioralDiff) -> dict[str, Any]:
    """Build the canonical behavioral-diff payload."""
    return {
        "state_changes": [
            {"path": item.path, "before": item.before, "after": item.after}
            for item in diff.state_changes
        ],
        "outcome_before": diff.outcome_before,
        "outcome_after": diff.outcome_after,
        "evidence_added": list(diff.evidence_added),
        "evidence_removed": list(diff.evidence_removed),
        "action_changes": [
            {
                "change_type": item.change_type,
                "before": item.before,
                "after": item.after,
            }
            for item in diff.action_changes
        ],
    }


def _discrepancy(diff: BehavioralDiff) -> tuple[str, ...]:
    """Return the discrepancy classification represented by the comparison."""
    result: list[str] = []
    if diff.state_changes:
        result.append("state_change")
    if diff.outcome_before != diff.outcome_after:
        result.append("outcome_change")
    if diff.evidence_added:
        result.append("evidence_added")
    if diff.evidence_removed:
        result.append("evidence_removed")
    if diff.action_changes:
        result.append("action_change")
    return tuple(result)


def _inputs(
    *,
    root: Path,
    before_state_path: Path,
    after_state_path: Path,
    before_evidence_path: Path | None,
    after_evidence_path: Path | None,
    before_events_path: Path | None,
    before_run_id: str | None,
    after_events_path: Path | None,
    after_run_id: str | None,
) -> tuple[
    tuple[ReliabilityComparisonInput, ...], tuple[ReliabilityComparisonInput, ...]
]:
    """Return the canonical input references for this comparison."""
    before_state = load_state(before_state_path)
    after_state = load_state(after_state_path)
    before: list[ReliabilityComparisonInput] = [
        ReliabilityComparisonInput(
            "before_state",
            "state",
            before_state.state_id,
            _file_digest(before_state_path),
            str(before_state_path.resolve().relative_to(root.resolve())),
        ),
    ]
    after: list[ReliabilityComparisonInput] = [
        ReliabilityComparisonInput(
            "after_state",
            "state",
            after_state.state_id,
            _file_digest(after_state_path),
            str(after_state_path.resolve().relative_to(root.resolve())),
        ),
    ]
    if before_evidence_path is not None:
        manifest = load_manifest(before_evidence_path)
        before.append(
            ReliabilityComparisonInput(
                "before_evidence",
                "evidence-manifest",
                manifest.manifest_id,
                _file_digest(before_evidence_path),
                str(before_evidence_path.resolve().relative_to(root.resolve())),
            )
        )
    if after_evidence_path is not None:
        manifest = load_manifest(after_evidence_path)
        after.append(
            ReliabilityComparisonInput(
                "after_evidence",
                "evidence-manifest",
                manifest.manifest_id,
                _file_digest(after_evidence_path),
                str(after_evidence_path.resolve().relative_to(root.resolve())),
            )
        )
    if before_events_path is not None and before_run_id:
        tuple(JsonlEventStore(before_events_path).validate_run(before_run_id))
        before.append(
            ReliabilityComparisonInput(
                "before_events",
                "run-events",
                before_run_id,
                _file_digest(before_events_path),
                str(before_events_path.resolve().relative_to(root.resolve())),
            )
        )
    if after_events_path is not None and after_run_id:
        tuple(JsonlEventStore(after_events_path).validate_run(after_run_id))
        after.append(
            ReliabilityComparisonInput(
                "after_events",
                "run-events",
                after_run_id,
                _file_digest(after_events_path),
                str(after_events_path.resolve().relative_to(root.resolve())),
            )
        )
    return tuple(before), tuple(after)


def build_reliability_behavioral_comparison(
    *,
    before_state_path: Path,
    after_state_path: Path,
    output: Path,
    before_evidence_path: Path | None = None,
    after_evidence_path: Path | None = None,
    before_events_path: Path | None = None,
    before_run_id: str | None = None,
    after_events_path: Path | None = None,
    after_run_id: str | None = None,
) -> ReliabilityBehavioralComparison:
    """Persist an immutable comparison artifact using the existing BehavioralDiff producer."""  # ruff: ignore[line-too-long]
    root = output.parent.resolve()
    before_inputs, after_inputs = _inputs(
        root=root,
        before_state_path=before_state_path,
        after_state_path=after_state_path,
        before_evidence_path=before_evidence_path,
        after_evidence_path=after_evidence_path,
        before_events_path=before_events_path,
        before_run_id=before_run_id,
        after_events_path=after_events_path,
        after_run_id=after_run_id,
    )
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
    diff = compare(
        before_state,
        after_state,
        before_evidence=before_evidence,
        after_evidence=after_evidence,
        before_events=before_events,
        after_events=after_events,
    )
    payload = {
        "format_version": "1",
        "before": [item.to_dict() for item in before_inputs],
        "after": [item.to_dict() for item in after_inputs],
        "diff": _diff_payload(diff),
        "significance": diff.risk,
        "discrepancy": list(_discrepancy(diff)),
    }
    comparison_id = sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    comparison = ReliabilityBehavioralComparison(
        comparison_id=comparison_id,
        before=before_inputs,
        after=after_inputs,
        diff=payload["diff"],  # type: ignore
        significance=diff.risk,
        discrepancy=tuple(payload["discrepancy"]),  # type: ignore
    )
    atomic_write_text(
        output, json.dumps(comparison.to_dict(), indent=2, sort_keys=True) + "\n"
    )
    return comparison


def comparison_input_references(
    comparison: ReliabilityBehavioralComparison,
) -> tuple[EvidenceReference, ...]:
    """Expose the exact source inputs represented by a comparison for proof/lineage closure."""  # ruff: ignore[line-too-long]
    return tuple(
        EvidenceReference(item.kind, item.identity, item.digest, item.source)
        for item in (*comparison.before, *comparison.after)
    )


def verify_reliability_behavioral_comparison(
    comparison: ReliabilityBehavioralComparison, *, root: Path
) -> None:
    """Recompute the existing BehavioralDiff and require exact semantic/source agreement."""  # ruff: ignore[line-too-long]
    root = root.resolve()

    def source(item: ReliabilityComparisonInput) -> Path:
        """Return the source reference associated with this comparison item."""
        path = _safe(root, item.source)
        if not path.is_file():
            raise FileNotFoundError(path)
        if _file_digest(path) != item.digest:
            raise ValueError(f"comparison source digest mismatch: {item.source}")
        return path

    before_state_path = source(
        next(item for item in comparison.before if item.role == "before_state")
    )
    after_state_path = source(
        next(item for item in comparison.after if item.role == "after_state")
    )
    before_evidence_item = next(
        (item for item in comparison.before if item.role == "before_evidence"), None
    )
    after_evidence_item = next(
        (item for item in comparison.after if item.role == "after_evidence"), None
    )
    before_events_item = next(
        (item for item in comparison.before if item.role == "before_events"), None
    )
    after_events_item = next(
        (item for item in comparison.after if item.role == "after_events"), None
    )
    before_evidence = (
        load_manifest(source(before_evidence_item)) if before_evidence_item else None
    )
    after_evidence = (
        load_manifest(source(after_evidence_item)) if after_evidence_item else None
    )
    before_events = (
        tuple(
            JsonlEventStore(source(before_events_item)).validate_run(
                before_events_item.identity
            )
        )
        if before_events_item
        else None
    )
    after_events = (
        tuple(
            JsonlEventStore(source(after_events_item)).validate_run(
                after_events_item.identity
            )
        )
        if after_events_item
        else None
    )
    diff = compare(
        load_state(before_state_path),
        load_state(after_state_path),
        before_evidence=before_evidence,
        after_evidence=after_evidence,
        before_events=before_events,
        after_events=after_events,
    )
    expected_diff = _diff_payload(diff)
    if comparison.diff != expected_diff:
        raise ValueError(
            "reliability behavioral comparison semantics do not match existing BehavioralDiff"
        )
    if comparison.significance != diff.risk:
        raise ValueError("reliability behavioral comparison significance mismatch")
    if comparison.discrepancy != _discrepancy(diff):
        raise ValueError("reliability behavioral comparison discrepancy mismatch")


def load_reliability_behavioral_comparison(
    path: Path,
) -> ReliabilityBehavioralComparison:
    """Load and validate a persisted reliability behavioral comparison."""
    payload = load_object(path)
    if not isinstance(payload, dict):
        raise ValueError("reliability behavioral comparison root must be an object")
    return ReliabilityBehavioralComparison.from_dict(payload)
