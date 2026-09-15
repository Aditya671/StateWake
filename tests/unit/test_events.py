"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

import unittest
from datetime import UTC, datetime

from statewake.domain.events import EventEnvelope


class EventEnvelopeTests(unittest.TestCase):
    """Provide regression coverage for the EventEnvelopeTests behavior."""

    def test_round_trip_preserves_canonical_event(self) -> None:
        """
        Verify the `test_round_trip_preserves_canonical_event`
        behavior and its expected invariants.
        """
        event = EventEnvelope(
            run_id="run-1",
            sequence=0,
            occurred_at=datetime(2026, 9, 9, 10, 0, tzinfo=UTC),
            event_type="run.started",
            actor="runtime",
            name="refund-agent",
            state_id="state-1",
            metadata={"z": "last", "a": "first"},
        )

        restored = EventEnvelope.from_dict(event.to_dict())
        self.assertEqual(restored, event)
        self.assertEqual(list(event.to_dict()["metadata"]), ["a", "z"])

    def test_naive_timestamp_is_rejected(self) -> None:
        """Verify the `test_naive_timestamp_is_rejected` behavior and its expected invariants."""
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            EventEnvelope(
                run_id="run-1",
                sequence=0,
                occurred_at=datetime(2026, 9, 9, 10, 0),  # noqa: DTZ001
                event_type="run.started",
                actor="runtime",
            )

    def test_required_fields_are_validated(self) -> None:
        """Verify the `test_required_fields_are_validated` behavior and its expected invariants."""
        with self.assertRaisesRegex(ValueError, "event_type"):
            EventEnvelope(
                run_id="run-1",
                sequence=0,
                occurred_at=datetime.now(UTC),
                event_type="",
                actor="runtime",
            )
