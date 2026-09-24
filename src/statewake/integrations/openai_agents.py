"""OpenAI Agents SDK trace mapping without importing the optional SDK."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from statewake.ai_contracts.model import ModelInvocationContract
from statewake.ai_contracts.runtime import RuntimeTraceContract
from statewake.ai_contracts.tool import ToolCallContract

from .base import (
    ContractCaptureResult,
    capture_contract,
    digest_json,
    json_object_from_mapping,
    mapping_from_object,
    metadata_without_payload,
    optional_string,
    parse_time,
    required_observed_mapping,
    required_observed_time,
    required_string,
)


def capture_openai_agent_trace(trace: object) -> ContractCaptureResult:
    """Map an OpenAI Agents trace-like object into runtime trace evidence."""
    data = mapping_from_object(trace)
    contract = RuntimeTraceContract(
        contract_version="openai_agents.runtime.v1",
        producer_id=required_string(
            data.get("producer_id", "openai-agents"), field="producer_id"
        ),
        run_id=required_string(
            data.get("run_id", data.get("trace_id")), field="run_id"
        ),
        framework="openai-agents",
        started_at=required_observed_time(data, field="start_time"),
        ended_at=required_observed_time(data, field="end_time"),
        captured_at=parse_time(data.get("captured_at")),
        trace_id=required_string(
            data.get("trace_id", data.get("run_id")), field="trace_id"
        ),
        span_id=required_string(
            data.get("span_id", data.get("run_id")), field="span_id"
        ),
        parent_run_id=optional_string(data.get("parent_run_id")),
        error_status=optional_string(data.get("error_status")),
        retry_of_run_id=optional_string(data.get("retry_of_run_id")),
        recovery_run_id=optional_string(data.get("recovery_of_run_id")),
        metadata=metadata_without_payload(data, exclude={"captured_at"}),
    )
    return capture_contract(contract)


def capture_openai_agent_model_event(event: Mapping[str, Any]) -> ContractCaptureResult:
    """Map an OpenAI Agents model event into model invocation evidence."""
    data = dict(event)
    model_version = optional_string(data.get("model_version"))
    contract = ModelInvocationContract(
        contract_version="openai_agents.model.v1",
        producer_id=required_string(
            data.get("producer_id", "openai-agents"), field="producer_id"
        ),
        run_id=required_string(data.get("run_id"), field="run_id"),
        provider=required_string(data.get("provider", "openai"), field="provider"),
        model_name=required_string(data.get("model_name"), field="model_name"),
        model_version=model_version,
        model_version_omission_reason=None
        if model_version is not None
        else "OpenAI Agents event did not include a model snapshot/version.",
        parameters=json_object_from_mapping(
            data.get("parameters", {}), field="parameters"
        ),
        request_digest=digest_json(required_observed_mapping(data, field="request")),
        response_digest=digest_json(required_observed_mapping(data, field="response")),
        finish_reason=optional_string(data.get("finish_reason")),
        captured_at=parse_time(data.get("captured_at")),
        metadata=metadata_without_payload(
            data,
            exclude={"request", "response", "parameters", "captured_at"},
        ),
    )
    return capture_contract(contract)


def capture_openai_agent_tool_event(event: Mapping[str, Any]) -> ContractCaptureResult:
    """Map an OpenAI Agents tool event into tool-call evidence."""
    data = dict(event)
    side_effect = required_string(
        data.get("side_effect_classification", "unknown"),
        field="side_effect_classification",
    )
    authorization = optional_string(data.get("authorization_decision"))
    if side_effect != "none" and authorization is None:
        authorization = "not-recorded-by-producer"
    contract = ToolCallContract(
        contract_version="openai_agents.tool.v1",
        producer_id=required_string(
            data.get("producer_id", "openai-agents"), field="producer_id"
        ),
        run_id=required_string(data.get("run_id"), field="run_id"),
        tool_name=required_string(data.get("tool_name"), field="tool_name"),
        schema_version=required_string(
            data.get("schema_version", "unknown"), field="schema_version"
        ),
        input_digest=digest_json(required_observed_mapping(data, field="input")),
        output_digest=digest_json(required_observed_mapping(data, field="output")),
        execution_status=required_string(
            data.get("execution_status", "unknown"), field="execution_status"
        ),
        side_effect_classification=side_effect,
        authorization_decision=authorization,
        captured_at=parse_time(data.get("captured_at")),
        metadata=metadata_without_payload(
            data,
            exclude={"input", "output", "captured_at"},
        ),
    )
    return capture_contract(contract)
