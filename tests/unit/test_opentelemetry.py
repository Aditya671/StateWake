"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

import unittest
from datetime import UTC, datetime

from statewake.adapters.opentelemetry import (
    OpenTelemetryTelemetrySink,
    export_recorded_run,
    extract_trace_context,
    inject_trace_context,
)
from statewake.domain.events import EventEnvelope


class FakeSpan:
    """Provide regression coverage for the FakeSpan behavior."""

    def __init__(self, name, attributes, start_time):
        """Initialize the test helper with its configured state."""
        self.name = name
        self.attributes = attributes
        self.start_time = start_time
        self.events = []
        self.status = None
        self.end_time = None

    def add_event(self, name, attributes=None, timestamp=None):
        """Verify the `add_event` behavior and its expected invariants."""
        self.events.append((name, attributes or {}, timestamp))

    def set_status(self, status):
        """Verify the `set_status` behavior and its expected invariants."""
        self.status = status

    def end(self, end_time=None):
        """Verify the `end` behavior and its expected invariants."""
        self.end_time = end_time


class FakeTracer:
    """Provide regression coverage for the FakeTracer behavior."""

    def __init__(self):
        """Initialize the test helper with its configured state."""
        self.spans = []

    def start_span(self, name, attributes=None, start_time=None):
        """Verify the `start_span` behavior and its expected invariants."""
        span = FakeSpan(name, attributes or {}, start_time)
        self.spans.append(span)
        return span


class OpenTelemetryTests(unittest.TestCase):
    """Provide regression coverage for the OpenTelemetryTests behavior."""

    EVENTS = [
        EventEnvelope(
            "otel-run",
            0,
            datetime(2026, 9, 9, 10, 0, tzinfo=UTC),
            "run.started",
            "runtime",
            name="refund-agent",
            state_id="state-1",
        ),
        EventEnvelope(
            "otel-run",
            1,
            datetime(2026, 9, 9, 10, 0, 1, tzinfo=UTC),
            "tool.called",
            "runtime",
            name="read_customer",
            metadata={"tool": "customer-crm"},
        ),
        EventEnvelope(
            "otel-run",
            2,
            datetime(2026, 9, 9, 10, 0, 2, tzinfo=UTC),
            "run.completed",
            "runtime",
            name="success",
            metadata={"outcome": "success"},
        ),
    ]

    def test_sink_maps_run_to_span_and_events(self) -> None:
        """
        Verify the `test_sink_maps_run_to_span_and_events` behavior
        and its expected invariants.
        """
        tracer = FakeTracer()
        sink = OpenTelemetryTelemetrySink(tracer)
        for event in self.EVENTS:
            sink.emit(event)
        sink.close()

        self.assertEqual(len(tracer.spans), 1)
        span = tracer.spans[0]
        self.assertEqual(span.name, "refund-agent")
        self.assertEqual(span.attributes["statewake.run_id"], "otel-run")
        self.assertEqual(span.attributes["statewake.state_id"], "state-1")
        self.assertEqual(
            [item[0] for item in span.events], ["tool.called", "run.completed"]
        )
        self.assertIsNotNone(span.end_time)
        self.assertIsNotNone(span.status)

    def test_export_recorded_run_closes_sink(self) -> None:
        """
        Verify the `test_export_recorded_run_closes_sink` behavior
        and its expected invariants.
        """
        tracer = FakeTracer()
        export_recorded_run(self.EVENTS, tracer)
        self.assertEqual(len(tracer.spans), 1)
        self.assertIsNotNone(tracer.spans[0].end_time)

    def test_non_start_event_requires_run_start(self) -> None:
        """
        Verify the `test_non_start_event_requires_run_start` behavior
        and its expected invariants.
        """
        sink = OpenTelemetryTelemetrySink(FakeTracer())
        with self.assertRaisesRegex(ValueError, "before run.started"):
            sink.emit(self.EVENTS[1])

    def test_context_propagation_round_trip_when_opentelemetry_is_available(
        self,
    ) -> None:
        """
        Verify the `test_context_propagation_round_trip_when_opentelemetry_is_available`
        behavior and its expected invariants.
        """
        try:
            from opentelemetry import trace
            from opentelemetry.trace import SpanContext, TraceFlags, TraceState
        except ImportError:
            self.skipTest("OpenTelemetry API is not installed.")

        context = trace.set_span_in_context(
            trace.NonRecordingSpan(
                SpanContext(
                    trace_id=1,
                    span_id=2,
                    is_remote=False,
                    trace_flags=TraceFlags(TraceFlags.SAMPLED),
                    trace_state=TraceState(),
                )
            )
        )
        carrier: dict[str, str] = {}
        inject_trace_context(carrier, context)
        extracted = extract_trace_context(carrier)
        extracted_span = trace.get_current_span(extracted)
        self.assertTrue(extracted_span.get_span_context().is_valid)
        self.assertEqual(extracted_span.get_span_context().trace_id, 1)
        self.assertEqual(extracted_span.get_span_context().span_id, 2)


if __name__ == "__main__":
    unittest.main()
