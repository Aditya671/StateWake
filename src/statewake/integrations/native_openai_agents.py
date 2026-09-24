"""Native OpenAI Agents tracing processor (SDK imported on construction)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from statewake.ai_contracts.model import ModelInvocationContract
from statewake.ai_contracts.tool import ToolCallContract
from statewake.integrations.base import capture_contract

from .native_capture import (
    NativeCaptureSink,
    capture_native_runtime,
    digest_observed,
    safe_metadata,
)


def create_agents_trace_processor(
    sink: NativeCaptureSink,
    *,
    tool_authorizations: dict[str, str] | None = None,
    side_effect_classifications: dict[str, str] | None = None,
) -> Any:
    """Build a real SDK TracingProcessor; register using agents.add_trace_processor.

    To prevent external export of sensitive traces, application owners must
    configure the SDK trace provider/export policy themselves. This processor
    stores only identifiers and status, not span payloads.
    """
    try:
        from agents.tracing.processor_interface import TracingProcessor
    except ModuleNotFoundError as exc:
        if exc.name is None or not (
            exc.name == "agents" or exc.name.startswith("agents.")
        ):
            raise
        raise ImportError(
            "Install statewake-ai[integrations-openai-agents] for native tracing"
        ) from exc

    class StateWakeAgentsProcessor(TracingProcessor):
        """Observe completed native trace and span lifecycles."""

        def __init__(self) -> None:
            self._trace_start: dict[str, datetime] = {}

        def on_trace_start(self, trace: Any) -> None:
            """Capture start time locally; the SDK Trace has no timestamp."""
            self._trace_start[str(trace.trace_id)] = datetime.now(UTC)

        def on_trace_end(self, trace: Any) -> None:
            """Capture completion of an actual Agents trace."""
            try:
                identity = str(trace.trace_id)
                started = self._trace_start.pop(identity, None)
                if started is None:
                    raise ValueError("trace completion lacks captured start")
                capture_native_runtime(
                    sink,
                    framework="openai-agents",
                    run_id=identity,
                    trace_id=identity,
                    span_id=identity,
                    started_at=started,
                    ended_at=datetime.now(UTC),
                    metadata=safe_metadata(event_kind="trace_end"),
                )
            except (ValueError, AttributeError, TypeError) as exc:
                sink.fail("agents.trace_end", exc)

        def on_span_start(self, span: Any) -> None:
            """No completion evidence is asserted for a started span."""

        def on_span_end(self, span: Any) -> None:
            """Capture an actual completed Agents span without raw span data."""
            try:
                trace_id = str(span.trace_id)
                span_id = str(span.span_id)
                error = getattr(span, "error", None)
                capture_native_runtime(
                    sink,
                    framework="openai-agents",
                    run_id=trace_id,
                    trace_id=trace_id,
                    span_id=span_id,
                    started_at=getattr(span, "started_at", None),
                    ended_at=getattr(span, "ended_at", None),
                    parent_run_id=getattr(span, "parent_id", None),
                    error_status="error" if error else None,
                    metadata=safe_metadata(
                        event_kind="span_end",
                        parent_span_id=getattr(span, "parent_id", None),
                    ),
                )
                data = getattr(span, "span_data", None)
                kind = getattr(data, "type", None)
                if error or data is None:
                    return
                if kind == "generation":
                    request = getattr(data, "input", None)
                    response = getattr(data, "output", None)
                    model_name = getattr(data, "model", None)
                    if request is None or response is None or not model_name:
                        sink.fail(
                            "agents.generation_missing",
                            ValueError("missing observation"),
                        )
                        return
                    try:
                        sink.add(
                            capture_contract(
                                ModelInvocationContract(
                                    contract_version="openai-agents.native.model.v1",
                                    producer_id="openai-agents-native",
                                    run_id=span_id,
                                    provider="not-recorded-by-producer",
                                    model_name=str(model_name),
                                    model_version=None,
                                    model_version_omission_reason="SDK span does not identify model snapshot",
                                    parameters={},
                                    request_digest=digest_observed(request),
                                    response_digest=digest_observed(response),
                                    finish_reason=None,
                                    captured_at=datetime.now(UTC),
                                    metadata={"trace_id": trace_id, "span_id": span_id},
                                )
                            )
                        )
                    except (ValueError, TypeError) as exc:
                        sink.fail("agents.generation_contract", exc)
                elif kind == "function":
                    name = getattr(data, "name", None)
                    request = getattr(data, "input", None)
                    response = getattr(data, "output", None)
                    classification = (side_effect_classifications or {}).get(str(name))
                    authorization = (tool_authorizations or {}).get(str(name))
                    if (
                        not name
                        or request is None
                        or response is None
                        or classification is None
                        or (classification != "none" and not authorization)
                    ):
                        sink.fail(
                            "agents.tool_missing",
                            ValueError("missing observation or policy"),
                        )
                        return
                    try:
                        sink.add(
                            capture_contract(
                                ToolCallContract(
                                    contract_version="openai-agents.native.tool.v1",
                                    producer_id="openai-agents-native",
                                    run_id=span_id,
                                    tool_name=str(name),
                                    schema_version="not-recorded-by-producer",
                                    input_digest=digest_observed(request),
                                    output_digest=digest_observed(response),
                                    execution_status="completed",
                                    side_effect_classification=classification,
                                    authorization_decision=authorization,
                                    captured_at=datetime.now(UTC),
                                    metadata={"trace_id": trace_id, "span_id": span_id},
                                )
                            )
                        )
                    except (ValueError, TypeError) as exc:
                        sink.fail("agents.tool_contract", exc)
            except (ValueError, AttributeError, TypeError) as exc:
                sink.fail("agents.span_end", exc)

        def shutdown(self) -> None:
            """Discard incomplete trace starts; keep completed evidence."""
            self._trace_start.clear()

        def force_flush(self) -> None:
            """Sink is synchronous; no buffered exporter remains."""

    return StateWakeAgentsProcessor()
