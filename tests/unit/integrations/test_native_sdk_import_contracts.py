"""Live SDK import/instantiation gates, skipped only if extra is absent."""

from __future__ import annotations

from typing import TypedDict

import pytest

from statewake.integrations.native_capture import NativeCaptureSink
from statewake.integrations.native_langchain import create_langchain_callback_handler
from statewake.integrations.native_llamaindex import create_llamaindex_event_handler
from statewake.integrations.native_openai_agents import create_agents_trace_processor
from statewake.integrations.native_opentelemetry import create_genai_span_processor


def test_real_openai_agents_processor_interface() -> None:
    pytest.importorskip("agents.tracing.processor_interface")
    from agents.tracing.processor_interface import TracingProcessor

    processor = create_agents_trace_processor(NativeCaptureSink())
    assert isinstance(processor, TracingProcessor)


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
