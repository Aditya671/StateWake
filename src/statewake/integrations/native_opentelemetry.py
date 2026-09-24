"""Real OpenTelemetry SDK SpanProcessor capturing completed native spans."""

from __future__ import annotations

from typing import Any

from .native_capture import NativeCaptureSink, capture_native_runtime, safe_metadata


def create_genai_span_processor(sink: NativeCaptureSink) -> Any:
    """Build an SDK SpanProcessor for registration on a TracerProvider."""
    try:
        from opentelemetry.sdk.trace import SpanProcessor
    except ModuleNotFoundError as exc:
        if exc.name is None or not (
            exc.name == "opentelemetry" or exc.name.startswith("opentelemetry.")
        ):
            raise
        raise ImportError(
            "Install statewake-ai[integrations-opentelemetry] for native tracing"
        ) from exc

    class StateWakeGenAISpanProcessor(SpanProcessor):
        """Observe completed OpenTelemetry spans without retaining raw attributes."""

        def on_start(self, span: Any, parent_context: Any = None) -> None:
            """Wait for on_end before claiming completion."""

        def on_end(self, span: Any) -> None:
            """Capture a completed sampled span and bounded GenAI identifiers."""
            try:
                context = span.get_span_context()
                if not context or not context.is_valid:
                    raise ValueError("span context is invalid")
                attributes = span.attributes or {}
                if not any(
                    key in attributes
                    for key in (
                        "gen_ai.operation.name",
                        "gen_ai.request.model",
                        "gen_ai.provider.name",
                        "gen_ai.system",
                    )
                ):
                    # Other SDK spans are outside the GenAI evidence scope.
                    return
                trace_id = format(context.trace_id, "032x")
                span_id = format(context.span_id, "016x")
                parent = getattr(span, "parent", None)
                capture_native_runtime(
                    sink,
                    framework="opentelemetry-genai",
                    run_id=str(attributes.get("statewake.run_id") or trace_id),
                    trace_id=trace_id,
                    span_id=span_id,
                    started_at=span.start_time,
                    ended_at=span.end_time,
                    parent_run_id=format(parent.span_id, "016x") if parent else None,
                    error_status="error"
                    if getattr(getattr(span, "status", None), "status_code", None)
                    and str(span.status.status_code).endswith("ERROR")
                    else None,
                    metadata=safe_metadata(
                        event_kind="span_end",
                        operation=attributes.get("gen_ai.operation.name"),
                        model_name=attributes.get("gen_ai.request.model"),
                        provider=attributes.get("gen_ai.provider.name"),
                    ),
                )
            except (ValueError, AttributeError, TypeError) as exc:
                sink.fail("opentelemetry.span_end", exc)

        def shutdown(self) -> None:
            """No asynchronous work to drain."""

        def force_flush(self, timeout_millis: int = 30000) -> bool:
            """Sink stores synchronously and has no pending exporter."""
            return True

    return StateWakeGenAISpanProcessor()
