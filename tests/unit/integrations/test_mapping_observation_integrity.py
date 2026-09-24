"""A missing observation cannot be replaced by a digest of empty content."""

from __future__ import annotations

import pytest

from statewake.integrations.langchain import capture_langchain_model_event
from statewake.integrations.langgraph import capture_langgraph_run_event
from statewake.integrations.llamaindex import capture_llamaindex_retrieval_event
from statewake.integrations.openai_agents import capture_openai_agent_tool_event
from statewake.integrations.opentelemetry_genai import capture_genai_model_invocation


def test_model_missing_response_is_not_an_observed_empty_response() -> None:
    with pytest.raises(ValueError, match="response was not observed"):
        capture_langchain_model_event(
            {
                "run_id": "r",
                "model_name": "m",
                "request": {},
            }
        )


def test_explicit_empty_response_is_a_real_distinct_observation() -> None:
    result = capture_langchain_model_event(
        {
            "run_id": "r",
            "model_name": "m",
            "request": {},
            "response": {},
        }
    )
    assert result.payload["request_digest"] == result.payload["response_digest"]


def test_tool_missing_output_fails_closed() -> None:
    with pytest.raises(ValueError, match="output was not observed"):
        capture_openai_agent_tool_event(
            {
                "run_id": "r",
                "tool_name": "lookup",
                "input": {},
                "side_effect_classification": "none",
                "execution_status": "success",
            }
        )


def test_retrieval_missing_query_fails_closed() -> None:
    with pytest.raises(ValueError, match="query was not observed"):
        capture_llamaindex_retrieval_event(
            {
                "run_id": "r",
                "corpus_identity": "c",
                "retrieved_item_ids": (),
            }
        )


def test_telemetry_model_missing_request_fails_closed() -> None:
    with pytest.raises(ValueError, match="request was not observed"):
        capture_genai_model_invocation(
            {
                "attributes": {
                    "statewake.run_id": "r",
                    "gen_ai.request.model": "m",
                    "response": {},
                }
            }
        )


def test_runtime_requires_actual_start_and_end() -> None:
    with pytest.raises(ValueError, match="start_time"):
        capture_langgraph_run_event(
            {"run_id": "r", "captured_at": "2026-09-23T00:00:00Z"}
        )
