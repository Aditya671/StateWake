"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from statewake.adapters.jsonl_store import JsonlEventStore
from statewake.domain.diff import compare
from statewake.domain.events import EventEnvelope
from statewake.domain.evidence import EvidenceItem, EvidenceManifest
from statewake.domain.state import SystemState
from statewake.services.diff_service import compare_artifacts


class DiffTests(unittest.TestCase):
    """Provide regression coverage for the DiffTests behavior."""

    def _state(self, **changes):
        """Verify the `_state` behavior and its expected invariants."""
        values = {
            "state_id": "state-a",
            "captured_at": datetime(2026, 9, 9, 10, 0, tzinfo=UTC),
            "agent_version": "agent@1",
            "model": "model@1",
            "prompt_digest": "prompt-a",
            "tool_digests": {"crm": "tool-a"},
            "retrieval_digest": "retrieval-a",
            "memory_digest": None,
            "policy_digest": "policy-a",
        }
        values.update(changes)
        return SystemState(**values)  # type: ignore

    def _events(self, run_id="run-a", outcome="success", tool="crm.read"):
        """Verify the `_events` behavior and its expected invariants."""
        return (
            EventEnvelope(
                run_id,
                0,
                datetime(2026, 9, 9, 10, 0, tzinfo=UTC),
                "run.started",
                "runtime",
            ),
            EventEnvelope(
                run_id,
                1,
                datetime(2026, 9, 9, 10, 0, 1, tzinfo=UTC),
                "tool.called",
                "agent",
                name=tool,
            ),
            EventEnvelope(
                run_id,
                2,
                datetime(2026, 9, 9, 10, 0, 2, tzinfo=UTC),
                "run.completed",
                "runtime",
                name=outcome,
            ),
        )

    def _manifest(self, ids):
        """Verify the `_manifest` behavior and its expected invariants."""
        return EvidenceManifest(
            "manifest",
            "run-a",
            tuple(
                EvidenceItem(item, "source", digest=f"digest-{item}") for item in ids
            ),
        )

    def test_identical_inputs_have_no_diff(self):
        """
        Verify the `test_identical_inputs_have_no_diff`
        behavior and its expected invariants.
        """
        result = compare(self._state(), self._state())
        self.assertFalse(result.changed)
        self.assertEqual(result.risk, "none")

    def test_state_diff_and_medium_risk_for_prompt_or_tool_change(self):
        """
        Verify the `test_state_diff_and_medium_risk_for_prompt_or_tool_change`
        behavior and its expected invariants.
        """
        result = compare(
            self._state(),
            self._state(prompt_digest="prompt-b", tool_digests={"crm": "tool-b"}),
        )
        self.assertEqual(
            {change.path for change in result.state_changes},
            {"prompt_digest", "tool_digests.crm"},
        )
        self.assertEqual(result.risk, "medium")

    def test_evidence_diff_is_low_risk(self):
        """
        Verify the `test_evidence_diff_is_low_risk`
        behavior and its expected invariants.
        """
        result = compare(
            self._state(),
            self._state(),
            before_evidence=self._manifest(["e1"]),
            after_evidence=self._manifest(["e2"]),
        )
        self.assertEqual(result.evidence_added, ("e2",))
        self.assertEqual(result.evidence_removed, ("e1",))
        self.assertEqual(result.risk, "low")

    def test_outcome_change_is_high_risk(self):
        """
        Verify the `test_outcome_change_is_high_risk`
        behavior and its expected invariants.
        """
        result = compare(
            self._state(),
            self._state(),
            before_events=self._events(outcome="success"),
            after_events=self._events(outcome="failed"),
        )
        self.assertEqual(result.outcome_before, "success")
        self.assertEqual(result.outcome_after, "failed")
        self.assertEqual(result.risk, "high")

    def test_action_add_remove_and_changed_are_structural(self):
        """
        Verify the `test_action_add_remove_and_changed_are_structural` behavior and
        its expected invariants.
        """
        changed = compare(
            self._state(),
            self._state(),
            before_events=self._events(tool="crm.read"),
            after_events=self._events(tool="crm.lookup"),
        )
        self.assertEqual(changed.risk, "medium")
        self.assertEqual(changed.action_changes[0].change_type, "changed")

        added = compare(
            self._state(),
            self._state(),
            before_events=self._events(),
            after_events=self._events()
            + (
                EventEnvelope(
                    "run-a",
                    3,
                    datetime(2026, 9, 9, 10, 0, 3, tzinfo=UTC),
                    "action.executed",
                    "agent",
                    name="refund.issue",
                ),
            ),
        )
        self.assertEqual(added.action_changes[-1].change_type, "added")
        self.assertEqual(added.risk, "high")

    def test_service_loads_state_evidence_and_events(self):
        """
        Verify the `test_service_loads_state_evidence_and_events`
        behavior and its expected invariants.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = root / "before.json"
            after = root / "after.json"
            evidence_before = root / "eb.json"
            evidence_after = root / "ea.json"
            before_events = root / "before.jsonl"
            after_events = root / "after.jsonl"
            before.write_text(
                __import__("json").dumps(self._state().to_dict()), encoding="utf-8"
            )
            after.write_text(
                __import__("json").dumps(self._state(model="model@2").to_dict()),
                encoding="utf-8",
            )
            evidence_before.write_text(
                __import__("json").dumps(self._manifest(["e1"]).to_dict()),
                encoding="utf-8",
            )
            evidence_after.write_text(
                __import__("json").dumps(self._manifest(["e1", "e2"]).to_dict()),
                encoding="utf-8",
            )
            for path in (before_events, after_events):
                store = JsonlEventStore(path)
                for event in self._events():
                    store.append(event)
            result = compare_artifacts(
                before,
                after,
                before_evidence_path=evidence_before,
                after_evidence_path=evidence_after,
                before_events_path=before_events,
                before_run_id="run-a",
                after_events_path=after_events,
                after_run_id="run-a",
            )
        self.assertEqual(result.risk, "medium")
        self.assertEqual(result.evidence_added, ("e2",))


if __name__ == "__main__":
    unittest.main()


class ActionAlignmentTests(unittest.TestCase):
    """Verify action diff alignment under insertions and explicit identities."""

    @staticmethod
    def _event(
        sequence: int, name: str, *, action_id: str | None = None
    ) -> EventEnvelope:
        """Create one action event with deterministic timing and optional identity."""
        metadata = {} if action_id is None else {"action_id": action_id}
        return EventEnvelope(
            "run-a",
            sequence,
            datetime(2026, 9, 9, 10, 0, 0, tzinfo=UTC),
            "action.executed",
            "agent",
            name=name,
            metadata=metadata,
        )

    @staticmethod
    def _states() -> tuple[SystemState, SystemState]:
        """Create equivalent states for action-only comparisons."""
        values = {
            "state_id": "state-a",
            "captured_at": datetime(2026, 9, 9, 10, 0, tzinfo=UTC),
            "agent_version": "agent@1",
            "model": "model@1",
            "prompt_digest": "prompt-a",
            "tool_digests": {},
            "retrieval_digest": "retrieval-a",
            "memory_digest": None,
            "policy_digest": "policy-a",
        }
        return SystemState(**values), SystemState(**values)  # type: ignore

    def test_middle_insertion_isolated_from_following_actions(self) -> None:
        """Verify an inserted action is reported without cascading false changes."""
        before = (
            self._event(1, "check_stock"),
            self._event(2, "approve"),
        )
        after = (
            self._event(1, "check_stock"),
            self._event(2, "flag_fraud_risk"),
            self._event(3, "approve"),
        )
        left, right = self._states()
        result = compare(left, right, before_events=before, after_events=after)
        self.assertEqual(
            [item.change_type for item in result.action_changes], ["added"]
        )
        self.assertEqual(result.action_changes[0].after["name"], "flag_fraud_risk")  # type: ignore

    def test_middle_deletion_isolated_from_following_actions(self) -> None:
        """Verify a deleted action is reported without cascading false changes."""
        before = (
            self._event(1, "check_stock"),
            self._event(2, "flag_fraud_risk"),
            self._event(3, "approve"),
        )
        after = (self._event(1, "check_stock"), self._event(2, "approve"))
        left, right = self._states()
        result = compare(left, right, before_events=before, after_events=after)
        self.assertEqual(
            [item.change_type for item in result.action_changes], ["removed"]
        )
        self.assertEqual(result.action_changes[0].before["name"], "flag_fraud_risk")  # type: ignore

    def test_explicit_action_identity_survives_content_change(self) -> None:
        """Verify an explicit action identity produces a precise changed event."""
        before = (self._event(1, "approve", action_id="a-1"),)
        after = (self._event(1, "reject", action_id="a-1"),)
        left, right = self._states()
        result = compare(left, right, before_events=before, after_events=after)
        self.assertEqual(
            [item.change_type for item in result.action_changes], ["changed"]
        )


def test_action_diff_isolates_seeded_insertions_and_deletions() -> None:
    """Exercise deterministic generated action mutations without positional smear."""
    base_state = ActionAlignmentTests._states()[0]
    base = [ActionAlignmentTests._event(index, f"action-{index}") for index in range(8)]
    for insertion in range(8):
        after = (
            base[:insertion]
            + [ActionAlignmentTests._event(99, "inserted")]
            + base[insertion:]
        )
        result = compare(
            base_state, base_state, before_events=tuple(base), after_events=tuple(after)
        )
        assert [item.change_type for item in result.action_changes] == ["added"]
        assert result.action_changes[0].after["name"] == "inserted"  # type: ignore
    for deletion in range(8):
        after = base[:deletion] + base[deletion + 1 :]
        result = compare(
            base_state, base_state, before_events=tuple(base), after_events=tuple(after)
        )
        assert [item.change_type for item in result.action_changes] == ["removed"]
        assert result.action_changes[0].before["name"] == f"action-{deletion}"  # type: ignore
