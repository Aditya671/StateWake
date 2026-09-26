"""Thin producer integrations that emit StateWake AI evidence contracts."""

from .base import (
    ContractCaptureResult,
    capture_contract,
    digest_json,
    profile_evidence_reference,
)
from .cicd import capture_cicd_release_event, capture_cicd_test_result
from .evaluators import capture_evaluator_result
from .langchain import (
    capture_langchain_model_event,
    capture_langchain_retriever_event,
    capture_langchain_tool_event,
)
from .langgraph import capture_langgraph_run_event
from .llamaindex import (
    capture_llamaindex_evaluator_event,
    capture_llamaindex_retrieval_event,
)
from .openai_agents import (
    capture_openai_agent_model_event,
    capture_openai_agent_tool_event,
    capture_openai_agent_trace,
)
from .opentelemetry_genai import (
    capture_genai_model_invocation,
    capture_genai_runtime_trace,
    capture_genai_tool_call,
)

__all__ = [
    "ContractCaptureResult",
    "capture_contract",
    "digest_json",
    "profile_evidence_reference",
    "capture_cicd_release_event",
    "capture_cicd_test_result",
    "capture_evaluator_result",
    "capture_langchain_model_event",
    "capture_langchain_retriever_event",
    "capture_langchain_tool_event",
    "capture_langgraph_run_event",
    "capture_llamaindex_evaluator_event",
    "capture_llamaindex_retrieval_event",
    "capture_openai_agent_model_event",
    "capture_openai_agent_tool_event",
    "capture_openai_agent_trace",
    "capture_genai_model_invocation",
    "capture_genai_runtime_trace",
    "capture_genai_tool_call",
]

# Native integrations import their SDKs only when constructed. They remain
# independently installable while sharing Phase 1 evidence contracts.
from .native_capture import (
    NativeCaptureCapacityError,
    NativeCaptureSink,
    capture_native_observation,
    capture_native_runtime,
)
from .native_langchain import create_langchain_callback_handler
from .native_langgraph import capture_langgraph_history
from .native_llamaindex import (
    attach_llamaindex_event_handler,
    create_llamaindex_event_handler,
    detach_llamaindex_event_handler,
)
from .native_openai_agents import create_agents_trace_processor
from .native_opentelemetry import create_genai_span_processor

__all__ += [
    "NativeCaptureSink",
    "NativeCaptureCapacityError",
    "capture_native_observation",
    "capture_native_runtime",
    "create_agents_trace_processor",
    "create_langchain_callback_handler",
    "capture_langgraph_history",
    "create_llamaindex_event_handler",
    "attach_llamaindex_event_handler",
    "detach_llamaindex_event_handler",
    "create_genai_span_processor",
]
