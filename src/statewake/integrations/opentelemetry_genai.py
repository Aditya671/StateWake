"""OpenTelemetry GenAI signal mapping into StateWake AI contracts."""

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


def _attributes(span: object) -> dict[str, Any]:
    data = mapping_from_object(span)
    raw_attributes = data.get("attributes", data)
    if isinstance(raw_attributes, Mapping):
        return dict(raw_attributes)
    return data


def capture_genai_runtime_trace(span: object) -> ContractCaptureResult:
    """Map an OpenTelemetry span-like object into a runtime trace contract."""
    attrs = _attributes(span)
    contract = RuntimeTraceContract(
        contract_version="opentelemetry.genai.runtime.v1",
        producer_id=required_string(
            attrs.get("statewake.producer_id", "opentelemetry-genai"),
            field="producer_id",
        ),
        run_id=required_string(
            attrs.get("statewake.run_id", attrs.get("gen_ai.operation.name")),
            field="run_id",
        ),
        framework="opentelemetry-genai",
        started_at=required_observed_time(attrs, field="start_time"),
        ended_at=required_observed_time(attrs, field="end_time"),
        captured_at=parse_time(attrs.get("captured_at")),
        trace_id=required_string(
            attrs.get(
                "trace_id",
                attrs.get("statewake.run_id", attrs.get("gen_ai.operation.name")),
            ),
            field="trace_id",
        ),
        span_id=required_string(
            attrs.get(
                "span_id",
                attrs.get("statewake.run_id", attrs.get("gen_ai.operation.name")),
            ),
            field="span_id",
        ),
        parent_run_id=optional_string(attrs.get("parent_run_id")),
        error_status=optional_string(attrs.get("error_status", attrs.get("status"))),
        retry_of_run_id=optional_string(attrs.get("retry_of_run_id")),
        recovery_run_id=optional_string(attrs.get("recovery_of_run_id")),
        metadata=metadata_without_payload(attrs, exclude={"captured_at"}),
    )
    return capture_contract(contract)


def capture_genai_model_invocation(span: object) -> ContractCaptureResult:
    """Map GenAI model span attributes into a model-invocation contract."""
    attrs = _attributes(span)
    request = required_observed_mapping(attrs, field="request")
    response = required_observed_mapping(attrs, field="response")
    model_version = optional_string(
        attrs.get("gen_ai.response.model", attrs.get("model_version"))
    )
    contract = ModelInvocationContract(
        contract_version="opentelemetry.genai.model.v1",
        producer_id=required_string(
            attrs.get("statewake.producer_id", "opentelemetry-genai"),
            field="producer_id",
        ),
        run_id=required_string(
            attrs.get("statewake.run_id", attrs.get("gen_ai.operation.name")),
            field="run_id",
        ),
        provider=required_string(
            attrs.get("gen_ai.system", attrs.get("provider", "unknown-provider")),
            field="provider",
        ),
        model_name=required_string(
            attrs.get("gen_ai.request.model", attrs.get("model_name")),
            field="model_name",
        ),
        model_version=model_version,
        model_version_omission_reason=None
        if model_version is not None
        else "OpenTelemetry span did not include a model snapshot/version.",
        parameters=json_object_from_mapping(
            attrs.get("parameters", {}), field="parameters"
        ),
        request_digest=digest_json(request),
        response_digest=digest_json(response),
        finish_reason=optional_string(attrs.get("finish_reason")),
        captured_at=parse_time(attrs.get("captured_at")),
        metadata=metadata_without_payload(
            attrs,
            exclude={"request", "response", "parameters", "captured_at"},
        ),
    )
    return capture_contract(contract)


def capture_genai_tool_call(event: Mapping[str, Any]) -> ContractCaptureResult:
    """Map a GenAI tool event into a tool-call contract."""
    data = dict(event)
    side_effect = required_string(
        data.get("side_effect_classification", "unknown"),
        field="side_effect_classification",
    )
    authorization = optional_string(data.get("authorization_decision"))
    if side_effect != "none" and authorization is None:
        authorization = "not-recorded-by-producer"
    contract = ToolCallContract(
        contract_version="opentelemetry.genai.tool.v1",
        producer_id=required_string(
            data.get("producer_id", "opentelemetry-genai"), field="producer_id"
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
