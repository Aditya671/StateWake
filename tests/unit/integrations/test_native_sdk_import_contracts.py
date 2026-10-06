"""Live SDK import/instantiation gates, skipped only if extra is absent."""

from __future__ import annotations

import json
from typing import TypedDict

import pytest

from statewake.integrations.native_capture import NativeCaptureSink
from statewake.integrations.native_langchain import create_langchain_callback_handler
from statewake.integrations.native_llamaindex import (
    attach_llamaindex_event_handler,
    create_llamaindex_event_handler,
    detach_llamaindex_event_handler,
)
from statewake.integrations.native_openai_agents import create_agents_trace_processor
from statewake.integrations.native_opentelemetry import create_genai_span_processor


def test_real_openai_agents_processor_interface() -> None:
    pytest.importorskip("agents.tracing.processor_interface")
    from agents.tracing.processor_interface import TracingProcessor

    processor = create_agents_trace_processor(NativeCaptureSink())
    assert isinstance(processor, TracingProcessor)


def test_real_openai_agents_native_span_lifecycle() -> None:
    """Exercise current SDK trace, generation, and function span objects offline."""
    pytest.importorskip("agents.tracing")
    from agents.tracing import (
        function_span,
        generation_span,
        set_trace_processors,
        set_tracing_disabled,
        trace,
    )

    sink = NativeCaptureSink()
    processor = create_agents_trace_processor(
        sink, side_effect_classifications={"statewake_qualify_tool": "none"}
    )
    set_tracing_disabled(False)
    set_trace_processors([processor])
    try:
        with trace("statewake-native-qualification"):
            with generation_span(
                input=[{"role": "user", "content": "private-input-marker"}],
                output=[{"role": "assistant", "content": "private-output-marker"}],
                model="statewake-qualification-model",
            ):
                pass
            with function_span(
                name="statewake_qualify_tool",
                input='{"value":"private-tool-input"}',
                output='{"ok":true,"value":"private-tool-output"}',
            ):
                pass
    finally:
        set_trace_processors([])

    payloads = [item.payload for item in sink.snapshot()]
    kinds = [payload["contract_type"] for payload in payloads]
    assert kinds.count("runtime_trace") == 3
    assert kinds.count("model_invocation") == 1
    assert kinds.count("tool_call") == 1
    assert not sink.failures
    persisted = json.dumps(payloads, sort_keys=True)
    for marker in (
        "private-input-marker",
        "private-output-marker",
        "private-tool-input",
        "private-tool-output",
    ):
        assert marker not in persisted


def test_real_langchain_callback_base() -> None:
    pytest.importorskip("langchain_core.callbacks.base")
    from langchain_core.callbacks.base import BaseCallbackHandler

    handler = create_langchain_callback_handler(NativeCaptureSink())
    assert isinstance(handler, BaseCallbackHandler)


def test_real_llamaindex_event_handler_base() -> None:
    pytest.importorskip("llama_index.core.instrumentation.event_handlers")
    from llama_index.core.instrumentation.event_handlers import BaseEventHandler

    handler = create_llamaindex_event_handler(NativeCaptureSink())
    assert isinstance(handler, BaseEventHandler)
    assert handler.class_name() == "StateWakeLlamaIndexHandler"


def test_real_llamaindex_root_dispatcher_attachment() -> None:
    """Qualify the current SDK root-dispatcher add/remove handler boundary."""
    pytest.importorskip("llama_index_instrumentation")
    from llama_index_instrumentation import get_dispatcher

    sink = NativeCaptureSink()
    dispatcher = get_dispatcher()
    before = tuple(getattr(dispatcher, "event_handlers", ()))
    handler = attach_llamaindex_event_handler(sink)
    try:
        assert handler in tuple(getattr(dispatcher, "event_handlers", ()))
    finally:
        detach_llamaindex_event_handler(handler)
    assert tuple(getattr(dispatcher, "event_handlers", ())) == before


def test_real_langgraph_checkpoint_api() -> None:
    pytest.importorskip("langgraph.graph")
    from langchain_core.runnables import RunnableConfig
    from langgraph.graph import END, START, StateGraph

    from statewake.integrations.native_capture import NativeCaptureSink
    from statewake.integrations.native_langgraph import capture_langgraph_history

    try:
        from langgraph.checkpoint.memory import MemorySaver
    except ImportError:
        pytest.fail("installed LangGraph lacks documented MemorySaver checkpoint API")

    class GraphState(TypedDict):
        probe: str

    def identity(state: GraphState) -> GraphState:
        return state

    graph = StateGraph(GraphState)
    graph.add_node("identity", identity)
    graph.add_edge(START, "identity")
    graph.add_edge("identity", END)
    compiled = graph.compile(checkpointer=MemorySaver())
    config: RunnableConfig = {
        "configurable": {"thread_id": "statewake-native-api-test"}
    }
    initial_state: GraphState = {"probe": "ok"}
    compiled.invoke(initial_state, config)
    sink = NativeCaptureSink()
    assert capture_langgraph_history(compiled, config, sink)
    assert not sink.failures


def test_real_opentelemetry_span_processor_base() -> None:
    pytest.importorskip("opentelemetry.sdk.trace")
    from opentelemetry.sdk.trace import SpanProcessor

    assert isinstance(create_genai_span_processor(NativeCaptureSink()), SpanProcessor)
