"""Native OpenAI Agents tracing processor (SDK imported on construction)."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from typing import Any

from statewake.ai_contracts.model import ModelInvocationContract
from statewake.ai_contracts.tool import ToolCallContract
from statewake.integrations.base import capture_contract

from .native_capture import (
    NativeCaptureSink,
    capture_native_runtime,
    digest_observed,
    digest_sdk_observed,
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
            self._completed_spans: set[tuple[str, str]] = set()
            self._span_lock = Lock()

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
            with self._span_lock:
                self._capture_span_end(span)

        def _capture_span_end(self, span: Any) -> None:
            """Admit one completion per native trace/span identity."""
            try:
                raw_trace_id = getattr(span, "trace_id", None)
                raw_span_id = getattr(span, "span_id", None)
                if not isinstance(raw_trace_id, str) or not raw_trace_id.strip():
                    raise ValueError("missing trace identity")
                if not isinstance(raw_span_id, str) or not raw_span_id.strip():
                    raise ValueError("missing span identity")
                trace_id = raw_trace_id
                span_id = raw_span_id
                identity = (trace_id, span_id)
                if identity in self._completed_spans:
                    return
                if len(self._completed_spans) >= sink.capacity:
                    sink.fail(
                        "agents.span_identity_capacity",
                        ValueError("completed span identity window exhausted"),
                    )
                    return
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
                self._completed_spans.add(identity)
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
                                    model_version_omission_reason=(
                                        "SDK span does not identify model snapshot"
                                    ),
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
                elif kind == "response":
                    request = getattr(data, "input", None)
                    response = getattr(data, "response", None)
                    model_name = getattr(response, "model", None)
                    if (
                        request is None
                        or response is None
                        or not isinstance(model_name, str)
                        or not model_name.strip()
                        or len(model_name) > 128
                        or not model_name.isprintable()
                    ):
                        sink.fail(
                            "agents.response_missing",
                            ValueError("missing observed response identity or content"),
                        )
                        return
                    try:
                        # Digest the entire JSON-mode SDK response envelope.
                        sink.add(
                            capture_contract(
                                ModelInvocationContract(
                                    contract_version="openai-agents.native.model.v1",
                                    producer_id="openai-agents-native",
                                    run_id=span_id,
                                    provider="not-recorded-by-producer",
                                    model_name=model_name,
                                    model_version=None,
                                    model_version_omission_reason=(
                                        "SDK response does not identify model snapshot"
                                    ),
                                    parameters={},
                                    request_digest=digest_sdk_observed(request),
                                    response_digest=digest_sdk_observed(response),
                                    finish_reason=None,
                                    captured_at=datetime.now(UTC),
                                    metadata={"trace_id": trace_id, "span_id": span_id},
                                )
                            )
                        )
                    except Exception as exc:
                        sink.fail("agents.response_contract", exc)
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
            with self._span_lock:
                self._completed_spans.clear()

        def force_flush(self) -> None:
            """Sink is synchronous; no buffered exporter remains."""

    return StateWakeAgentsProcessor()
