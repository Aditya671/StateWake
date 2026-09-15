"""Deterministic behavioral comparison primitives."""

from dataclasses import dataclass
from typing import Any, TypeVar, cast

from ..domain.events import EventEnvelope
from ..domain.evidence import EvidenceManifest
from ..domain.state import SystemState

KeyT = TypeVar("KeyT")


@dataclass(frozen=True, slots=True)
class FieldChange:
    """One changed field between two behavioral artifacts."""

    path: str
    before: Any
    after: Any


@dataclass(frozen=True, slots=True)
class ActionChange:
    """One added, removed, or changed action/decision event."""

    change_type: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class BehavioralDiff:
    """Deterministic comparison of two runs and their associated artifacts."""

    state_changes: tuple[FieldChange, ...] = ()
    outcome_before: str | None = None
    outcome_after: str | None = None
    evidence_added: tuple[str, ...] = ()
    evidence_removed: tuple[str, ...] = ()
    action_changes: tuple[ActionChange, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize the behavioral diff into a stable diagnostic mapping."""
        return {
            "state_changes": [
                {"path": item.path, "before": item.before, "after": item.after}
                for item in self.state_changes
            ],
            "outcome_before": self.outcome_before,
            "outcome_after": self.outcome_after,
            "evidence_added": list(self.evidence_added),
            "evidence_removed": list(self.evidence_removed),
            "action_changes": [
                {
                    "change_type": item.change_type,
                    "before": item.before,
                    "after": item.after,
                }
                for item in self.action_changes
            ],
            "changed": self.changed,
            "risk": self.risk,
        }

    @property
    def changed(self) -> bool:
        """Whether this comparison contains a material change."""
        return bool(
            self.state_changes
            or self.outcome_before != self.outcome_after
            or self.evidence_added
            or self.evidence_removed
            or self.action_changes
        )

    @property
    def risk(self) -> str:
        """Classify behavioral significance without semantic model inference."""
        if self.outcome_before != self.outcome_after:
            return "high"
        if self.action_changes:
            return (
                "high"
                if any(
                    change.change_type in {"added", "removed"}
                    for change in self.action_changes
                )
                else "medium"
            )
        if self.state_changes:
            critical = {"model", "prompt_digest", "policy_digest", "retrieval_digest"}
            if any(
                change.path in critical or change.path.startswith("tool_digests.")
                for change in self.state_changes
            ):
                return "medium"
            return "low"
        if self.evidence_added or self.evidence_removed:
            return "low"
        return "none"


def _state_changes(before: SystemState, after: SystemState) -> tuple[FieldChange, ...]:
    """Return the state changes represented by this behavioral diff."""
    left = before.fingerprint_payload()
    right = after.fingerprint_payload()
    changes: list[FieldChange] = []
    keys = sorted(set(left) | set(right))
    for key in keys:
        before_value = left.get(key)
        after_value = right.get(key)
        if isinstance(before_value, dict) and isinstance(after_value, dict):
            before_mapping = cast(dict[str, Any], before_value)
            after_mapping = cast(dict[str, Any], after_value)
            for child in sorted(set(before_mapping) | set(after_mapping)):
                if before_mapping.get(child) != after_mapping.get(child):
                    changes.append(
                        FieldChange(
                            f"{key}.{child}",
                            before_mapping.get(child),
                            after_mapping.get(child),
                        )
                    )
        elif before_value != after_value:
            changes.append(FieldChange(key, before_value, after_value))
    return tuple(changes)


def _evidence_ids(manifest: EvidenceManifest | None) -> frozenset[str]:
    """Return evidence identities associated with this behavioral diff."""
    return (
        frozenset(item.evidence_id for item in manifest.items)
        if manifest
        else frozenset()
    )


def _outcome(events: tuple[EventEnvelope, ...] | None) -> str | None:
    """Return the outcome represented by this behavioral diff."""
    if not events:
        return None
    for event in reversed(events):
        if event.event_type == "run.completed":
            return event.metadata.get("outcome") or event.name or "completed"
    terminal = events[-1]
    return terminal.metadata.get("outcome") or terminal.name or terminal.event_type


def _action_events(
    events: tuple[EventEnvelope, ...] | None,
) -> tuple[EventEnvelope, ...]:
    """Return action events represented by this behavioral diff."""
    if not events:
        return ()
    prefixes = ("action.", "decision.")
    exact = {"tool.called", "tool.returned"}
    return tuple(
        event
        for event in events
        if event.event_type.startswith(prefixes) or event.event_type in exact
    )


def _action_identity(event: EventEnvelope) -> tuple[str, ...]:
    """Return a stable structural key for aligning comparable action events."""
    for key in ("action_id", "tool_call_id", "decision_id", "event_id"):
        value = event.metadata.get(key)
        if value:
            return ("id", key, value)
    return (
        "shape",
        event.event_type,
        event.actor,
        event.state_id or "",
        event.payload_ref or "",
    )


def _action_payload(event: EventEnvelope) -> dict[str, Any]:
    """Return action content excluding the sequence position used for ordering."""
    payload = event.to_dict()
    payload.pop("sequence", None)
    payload.pop("occurred_at", None)
    return payload


def _lcs_matches(
    left_keys: tuple[KeyT, ...], right_keys: tuple[KeyT, ...]
) -> tuple[tuple[int, int], ...]:
    """Return deterministic longest-common-subsequence matches."""
    rows = len(left_keys) + 1
    columns = len(right_keys) + 1
    lengths = [[0] * columns for _ in range(rows)]
    for left_index in range(len(left_keys) - 1, -1, -1):
        for right_index in range(len(right_keys) - 1, -1, -1):
            if left_keys[left_index] == right_keys[right_index]:
                lengths[left_index][right_index] = (
                    1 + lengths[left_index + 1][right_index + 1]
                )
            else:
                lengths[left_index][right_index] = max(
                    lengths[left_index + 1][right_index],
                    lengths[left_index][right_index + 1],
                )

    matches: list[tuple[int, int]] = []
    left_index = right_index = 0
    while left_index < len(left_keys) and right_index < len(right_keys):
        if left_keys[left_index] == right_keys[right_index]:
            matches.append((left_index, right_index))
            left_index += 1
            right_index += 1
        elif (
            lengths[left_index + 1][right_index] >= lengths[left_index][right_index + 1]
        ):
            left_index += 1
        else:
            right_index += 1
    return tuple(matches)


def _action_alignment(
    left: tuple[EventEnvelope, ...], right: tuple[EventEnvelope, ...]
) -> tuple[tuple[int | None, int | None], ...]:
    """Align actions by exact content, stable identity, then position."""
    left_keys = tuple(repr(_action_payload(event)) for event in left)
    right_keys = tuple(repr(_action_payload(event)) for event in right)
    exact_matches = _lcs_matches(left_keys, right_keys)
    anchors = ((-1, -1), *exact_matches, (len(left), len(right)))

    alignment: list[tuple[int | None, int | None]] = []
    for (left_start, right_start), (left_end, right_end) in zip(
        anchors, anchors[1:], strict=False
    ):
        left_gap = list(range(left_start + 1, left_end))
        right_gap = list(range(right_start + 1, right_end))
        left_identities = tuple(_action_identity(left[index]) for index in left_gap)
        right_identities = tuple(_action_identity(right[index]) for index in right_gap)
        identity_matches = _lcs_matches(left_identities, right_identities)
        gap_anchors = ((-1, -1), *identity_matches, (len(left_gap), len(right_gap)))
        for (left_gap_start, right_gap_start), (left_gap_end, right_gap_end) in zip(
            gap_anchors, gap_anchors[1:], strict=False
        ):
            left_residual = left_gap[left_gap_start + 1 : left_gap_end]
            right_residual = right_gap[right_gap_start + 1 : right_gap_end]
            common = min(len(left_residual), len(right_residual))
            alignment.extend(
                (left_residual[index], right_residual[index]) for index in range(common)
            )
            alignment.extend((index, None) for index in left_residual[common:])
            alignment.extend((None, index) for index in right_residual[common:])
            if left_gap_end < len(left_gap) and right_gap_end < len(right_gap):
                alignment.append((left_gap[left_gap_end], right_gap[right_gap_end]))
        if left_end < len(left) and right_end < len(right):
            alignment.append((left_end, right_end))
    return tuple(alignment)


def _action_changes(
    before: tuple[EventEnvelope, ...] | None, after: tuple[EventEnvelope, ...] | None
) -> tuple[ActionChange, ...]:
    """Return action changes using stable structural sequence alignment."""
    left = _action_events(before)
    right = _action_events(after)
    changes: list[ActionChange] = []
    for left_index, right_index in _action_alignment(left, right):
        left_action = None if left_index is None else left[left_index].to_dict()
        right_action = None if right_index is None else right[right_index].to_dict()
        if left_action is None:
            changes.append(ActionChange("added", None, right_action))
        elif right_action is None:
            changes.append(ActionChange("removed", left_action, None))
        else:
            assert left_index is not None and right_index is not None
            if _action_payload(left[left_index]) != _action_payload(right[right_index]):
                changes.append(ActionChange("changed", left_action, right_action))
    return tuple(changes)


def compare(
    before_state: SystemState,
    after_state: SystemState,
    *,
    before_evidence: EvidenceManifest | None = None,
    after_evidence: EvidenceManifest | None = None,
    before_events: tuple[EventEnvelope, ...] | None = None,
    after_events: tuple[EventEnvelope, ...] | None = None,
) -> BehavioralDiff:
    """Compare deterministic behavioral evidence without semantic model inference."""
    before_ids = _evidence_ids(before_evidence)
    after_ids = _evidence_ids(after_evidence)
    return BehavioralDiff(
        state_changes=_state_changes(before_state, after_state),
        outcome_before=_outcome(before_events),
        outcome_after=_outcome(after_events),
        evidence_added=tuple(sorted(after_ids - before_ids)),
        evidence_removed=tuple(sorted(before_ids - after_ids)),
        action_changes=_action_changes(before_events, after_events),
    )
