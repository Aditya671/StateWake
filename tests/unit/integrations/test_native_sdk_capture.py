"""Native callback and checkpoint regression tests using actual SDK when installed."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from statewake.integrations import (
    NativeCaptureSink,
    capture_langgraph_history,
    create_agents_trace_processor,
    create_genai_span_processor,
    create_langchain_callback_handler,
    create_llamaindex_event_handler,
)


def test_native_sink_rejects_unobserved_success_and_redacts_failures() -> None:
    sink = NativeCaptureSink()
    sink.fail("tool", ValueError("secret-token=very-secret"))
    assert sink.snapshot() == ()
    assert sink.failures == ["tool: ValueError"]
    assert "very-secret" not in repr(sink.failures)


def test_openai_processor_registers_native_lifecycle_without_payload() -> None:
    agents = ModuleType("agents")
    tracing = ModuleType("agents.tracing")

    class TracingProcessor:
        pass

    tracing.TracingProcessor = TracingProcessor  # type: ignore[attr-defined]
    processor_interface = ModuleType("agents.tracing.processor_interface")
    processor_interface.TracingProcessor = TracingProcessor  # type: ignore[attr-defined]
    with patch.dict(
        sys.modules,
        {
            "agents": agents,
            "agents.tracing": tracing,
            "agents.tracing.processor_interface": processor_interface,
        },
    ):
        sink = NativeCaptureSink()
        processor = create_agents_trace_processor(sink)
        processor.on_trace_start(SimpleNamespace(trace_id="t"))
        assert not sink.snapshot()
        span = SimpleNamespace(
            trace_id="trace-1",
            span_id="span-1",
            parent_id="parent-1",
            started_at="2026-09-23T00:00:00+00:00",
            ended_at="2026-09-23T00:00:01+00:00",
            error=None,
            data={"prompt": "sensitive secret"},
        )
        processor.on_span_end(span)
        result = sink.snapshot()[0]
        assert result.payload["trace_id"] == "trace-1"
        assert result.payload["span_id"] == "span-1"
        assert result.payload["parent_run_id"] == "parent-1"
        assert "sensitive secret" not in str(result.payload)


def test_langchain_callback_pairs_tool_start_and_end_without_raw_input() -> None:
    langchain_core = ModuleType("langchain_core")
    callbacks = ModuleType("langchain_core.callbacks")

    class BaseCallbackHandler:
        pass

    callbacks.BaseCallbackHandler = BaseCallbackHandler  # type: ignore[attr-defined]
    callback_base = ModuleType("langchain_core.callbacks.base")
    callback_base.BaseCallbackHandler = BaseCallbackHandler  # type: ignore[attr-defined]
    with patch.dict(
        sys.modules,
        {
            "langchain_core": langchain_core,
            "langchain_core.callbacks": callbacks,
            "langchain_core.callbacks.base": callback_base,
        },
    ):
        sink = NativeCaptureSink()
        handler = create_langchain_callback_handler(
            sink, side_effect_classifications={"search": "none"}
        )
        run_id = uuid4()
        handler.on_tool_start({"name": "search"}, "secret-input", run_id=run_id)
        assert not sink.snapshot()
        handler.on_tool_end("secret-output", run_id=run_id)
        assert len(sink.snapshot()) == 2
        assert sink.snapshot()[0].payload["contract_type"] == "tool_call"
        assert sink.snapshot()[1].payload["metadata"]["event_kind"] == "tool"
        assert "secret-input" not in str(sink.snapshot()[0].payload)
        assert "secret-output" not in str(sink.snapshot()[0].payload)
        handler.on_tool_end("no start", run_id=run_id)
        assert sink.failures == ["langchain.unpaired_callback: ValueError"]


def test_llamaindex_handler_captures_event_without_payload() -> None:
    parent = ModuleType("llama_index")
    core = ModuleType("llama_index.core")
    instrumentation = ModuleType("llama_index.core.instrumentation")
    events = ModuleType("llama_index.core.instrumentation.event_handlers")

    class BaseEventHandler:
        pass

    events.BaseEventHandler = BaseEventHandler  # type: ignore[attr-defined]
    with patch.dict(
        sys.modules,
        {
            "llama_index": parent,
            "llama_index.core": core,
            "llama_index.core.instrumentation": instrumentation,
            "llama_index.core.instrumentation.event_handlers": events,
        },
    ):
        sink = NativeCaptureSink()
        handler = create_llamaindex_event_handler(sink)
        event = SimpleNamespace(
            id_="event-1", timestamp="2026-09-23T00:00:00+00:00", text="secret"
        )
        event.class_name = lambda: "RetrievalEndEvent"
        handler.handle(event)
        assert (
            sink.snapshot()[0].payload["metadata"]["operation"] == "RetrievalEndEvent"
        )
        assert "secret" not in str(sink.snapshot()[0].payload)


def test_langgraph_history_binds_checkpoint_and_state_digest() -> None:
    snapshot = SimpleNamespace(
        values={"answer": "hello"},
        config={"configurable": {"thread_id": "thread-1", "checkpoint_id": "ckpt-1"}},
        parent_config={"configurable": {"checkpoint_id": "ckpt-0"}},
        created_at="2026-09-23T00:00:00+00:00",
        tasks=(),
        interrupts=(),
    )

    class Graph:
        def get_state_history(
            self, config: object, *, limit: object = None
        ) -> list[object]:
            return [snapshot]

    sink = NativeCaptureSink()
    results = capture_langgraph_history(
        Graph(), {"configurable": {"thread_id": "thread-1"}}, sink
    )
    assert len(results) == 1
    assert results[0].payload["span_id"] == "ckpt-1"
    assert results[0].payload["metadata"]["parent_checkpoint_id"] == "ckpt-0"
    assert "hello" not in str(results[0].payload)


def test_real_opentelemetry_sdk_completed_span() -> None:
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.trace import Status, StatusCode

    sink = NativeCaptureSink()
    provider = TracerProvider()
    provider.add_span_processor(create_genai_span_processor(sink))
    tracer = provider.get_tracer("statewake-native-test")
    with tracer.start_as_current_span("chat") as span:
        span.set_attribute("statewake.run_id", "native-run")
        span.set_attribute("gen_ai.operation.name", "chat")
        span.set_attribute("gen_ai.request.model", "model-1")
        span.set_attribute("gen_ai.input.messages", "sensitive message")
        span.set_status(Status(StatusCode.ERROR))
    results = sink.snapshot()
    assert len(results) == 1, sink.failures
    assert results[0].payload["run_id"] == "native-run"
    assert results[0].payload["error_status"] == "error"
    assert "sensitive message" not in str(results[0].payload)
    provider.shutdown()


def test_openai_native_generation_and_function_contracts() -> None:
    """Observed SDK span data produce contracts only when fields and policy exist."""
    agents = ModuleType("agents")
    tracing = ModuleType("agents.tracing")

    class TracingProcessor:
        pass

    tracing.TracingProcessor = TracingProcessor  # type: ignore[attr-defined]
    processor_interface = ModuleType("agents.tracing.processor_interface")
    processor_interface.TracingProcessor = TracingProcessor  # type: ignore[attr-defined]
    with patch.dict(
        sys.modules,
        {
            "agents": agents,
            "agents.tracing": tracing,
            "agents.tracing.processor_interface": processor_interface,
        },
    ):
        sink = NativeCaptureSink()
        processor = create_agents_trace_processor(
            sink,
            side_effect_classifications={"lookup": "none"},
        )
        processor.on_trace_start(SimpleNamespace(trace_id="trace-2"))
        processor.on_trace_end(SimpleNamespace(trace_id="trace-2"))
        assert sink.snapshot()[0].payload["metadata"]["event_kind"] == "trace_end"
        for kind, data in (
            (
                "generation",
                SimpleNamespace(
                    type="generation",
                    model="test-model",
                    input=[{"text": "secret"}],
                    output=[{"text": "private"}],
                ),
            ),
            (
                "function",
                SimpleNamespace(
                    type="function", name="lookup", input="sensitive", output="private"
                ),
            ),
        ):
            span = SimpleNamespace(
                trace_id="trace-2",
                span_id=f"span-{kind}",
                parent_id=None,
                started_at="2026-09-23T00:00:00+00:00",
                ended_at="2026-09-23T00:00:01+00:00",
                error=None,
                span_data=data,
            )
            processor.on_span_end(span)
        types = [result.payload["contract_type"] for result in sink.snapshot()]
        assert types.count("runtime_trace") == 3
        assert "model_invocation" in types
        assert "tool_call" in types
        assert not sink.failures
        assert "secret" not in str([result.payload for result in sink.snapshot()])
        assert "private" not in str([result.payload for result in sink.snapshot()])


def test_llamaindex_native_retrieval_with_real_node_shape() -> None:
    parent = ModuleType("llama_index")
    core = ModuleType("llama_index.core")
    instrumentation = ModuleType("llama_index.core.instrumentation")
    events = ModuleType("llama_index.core.instrumentation.event_handlers")

    class BaseEventHandler:
        pass

    events.BaseEventHandler = BaseEventHandler  # type: ignore[attr-defined]
    with patch.dict(
        sys.modules,
        {
            "llama_index": parent,
            "llama_index.core": core,
            "llama_index.core.instrumentation": instrumentation,
            "llama_index.core.instrumentation.event_handlers": events,
        },
    ):
        sink = NativeCaptureSink()
        handler = create_llamaindex_event_handler(
            sink,
            corpus_identity="corpus-1",
            corpus_snapshot_id="snapshot-1",
            citation_boundary="node-ids",
        )
        node = SimpleNamespace(node_id="node-1", get_content=lambda: "private chunk")
        event = SimpleNamespace(
            id_="event-99",
            span_id="span-99",
            str_or_query_bundle="private query",
            nodes=[SimpleNamespace(node=node)],
            timestamp="2026-09-23T00:00:00+00:00",
        )
        event.class_name = lambda: "RetrievalEndEvent"
        handler.handle(event)
        assert [entry.payload["contract_type"] for entry in sink.snapshot()] == [
            "retrieval",
            "observation",
        ]
        assert sink.snapshot()[0].payload["retrieved_item_ids"] == ["node-1"]
        assert "private chunk" not in str(sink.snapshot()[0].payload)
        assert "private query" not in str(sink.snapshot()[0].payload)


def test_langchain_model_and_retrieval_contracts_require_observed_content() -> None:
    """Native callback content produces digest-bound contracts and safe metadata."""
    langchain_core = ModuleType("langchain_core")
    callbacks = ModuleType("langchain_core.callbacks")

    class BaseCallbackHandler:
        pass

    callbacks.BaseCallbackHandler = BaseCallbackHandler  # type: ignore[attr-defined]
    callback_base = ModuleType("langchain_core.callbacks.base")
    callback_base.BaseCallbackHandler = BaseCallbackHandler  # type: ignore[attr-defined]
    with patch.dict(
        sys.modules,
        {
            "langchain_core": langchain_core,
            "langchain_core.callbacks": callbacks,
            "langchain_core.callbacks.base": callback_base,
        },
    ):
        sink = NativeCaptureSink()
        handler = create_langchain_callback_handler(
            sink,
            corpus_identity="corpus-1",
            corpus_snapshot_id="snapshot-1",
            citation_boundary="doc-id",
        )
        model_run = uuid4()
        handler.on_llm_start(
            {"name": "local-model"}, ["secret prompt"], run_id=model_run
        )
        handler.on_llm_end("private answer", run_id=model_run)
        retrieval_run = uuid4()
        handler.on_retriever_start(
            {"name": "retriever"}, "private query", run_id=retrieval_run
        )
        handler.on_retriever_end(
            [SimpleNamespace(id="doc-1", page_content="private chunk")],
            run_id=retrieval_run,
        )
        kinds = [result.payload["contract_type"] for result in sink.snapshot()]
        assert kinds == [
            "model_invocation",
            "runtime_trace",
            "retrieval",
            "runtime_trace",
        ]
        assert sink.snapshot()[2].payload["retrieved_item_ids"] == ["doc-1"]
        assert not sink.failures
        assert "private chunk" not in str(
            [result.payload for result in sink.snapshot()]
        )
        assert "secret prompt" not in str(
            [result.payload for result in sink.snapshot()]
        )


def test_langchain_tool_missing_authorization_is_not_approved() -> None:
    """Runtime completion does not imply authorization for side-effecting tools."""
    langchain_core = ModuleType("langchain_core")
    callbacks = ModuleType("langchain_core.callbacks")

    class BaseCallbackHandler:
        pass

    callbacks.BaseCallbackHandler = BaseCallbackHandler  # type: ignore[attr-defined]
    callback_base = ModuleType("langchain_core.callbacks.base")
    callback_base.BaseCallbackHandler = BaseCallbackHandler  # type: ignore[attr-defined]
    with patch.dict(
        sys.modules,
        {
            "langchain_core": langchain_core,
            "langchain_core.callbacks": callbacks,
            "langchain_core.callbacks.base": callback_base,
        },
    ):
        sink = NativeCaptureSink()
        handler = create_langchain_callback_handler(
            sink, side_effect_classifications={"send_email": "external_write"}
        )
        run_id = uuid4()
        handler.on_tool_start({"name": "send_email"}, "private message", run_id=run_id)
        handler.on_tool_end("sent", run_id=run_id)
        assert [result.payload["contract_type"] for result in sink.snapshot()] == [
            "runtime_trace"
        ]
        assert sink.failures == ["langchain.tool_authorization: ValueError"]
