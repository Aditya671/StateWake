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
