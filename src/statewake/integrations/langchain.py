"""LangChain callback-style event mapping into StateWake contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from statewake.ai_contracts.model import ModelInvocationContract
from statewake.ai_contracts.retrieval import RetrievalEvidenceContract
from statewake.ai_contracts.tool import ToolCallContract

from .base import (
    ContractCaptureResult,
    capture_contract,
    digest_json,
    json_object_from_mapping,
    metadata_without_payload,
    optional_string,
    parse_time,
    required_string,
)


def capture_langchain_model_event(event: Mapping[str, Any]) -> ContractCaptureResult:
    """Map a LangChain model callback event into model invocation evidence."""
    data = dict(event)
    model_version = optional_string(data.get("model_version"))
    contract = ModelInvocationContract(
        contract_version="langchain.model.v1",
        producer_id=required_string(
            data.get("producer_id", "langchain"), field="producer_id"
        ),
        run_id=required_string(data.get("run_id"), field="run_id"),
        provider=required_string(
            data.get("provider", "unknown-provider"), field="provider"
        ),
        model_name=required_string(data.get("model_name"), field="model_name"),
        model_version=model_version,
        model_version_omission_reason=None
        if model_version
        else "LangChain event did not include a model snapshot/version.",
        parameters=json_object_from_mapping(
            data.get("parameters", {}), field="parameters"
        ),
        request_digest=digest_json(
            json_object_from_mapping(data.get("request", {}), field="request")
        ),
        response_digest=digest_json(
            json_object_from_mapping(data.get("response", {}), field="response")
        ),
        finish_reason=optional_string(data.get("finish_reason")),
        captured_at=parse_time(data.get("captured_at")),
        metadata=metadata_without_payload(
            data, exclude={"request", "response", "parameters", "captured_at"}
        ),
    )
    return capture_contract(contract)


def capture_langchain_tool_event(event: Mapping[str, Any]) -> ContractCaptureResult:
    """Map a LangChain tool callback event into tool-call evidence."""
    data = dict(event)
    side_effect = required_string(
        data.get("side_effect_classification", "unknown"),
        field="side_effect_classification",
    )
    authorization = optional_string(data.get("authorization_decision"))
    if side_effect != "none" and authorization is None:
        authorization = "not-recorded-by-producer"
    contract = ToolCallContract(
        contract_version="langchain.tool.v1",
        producer_id=required_string(
            data.get("producer_id", "langchain"), field="producer_id"
        ),
        run_id=required_string(data.get("run_id"), field="run_id"),
        tool_name=required_string(data.get("tool_name"), field="tool_name"),
        schema_version=required_string(
            data.get("schema_version", "unknown"), field="schema_version"
        ),
        input_digest=digest_json(
            json_object_from_mapping(data.get("input", {}), field="input")
        ),
        output_digest=digest_json(
            json_object_from_mapping(data.get("output", {}), field="output")
        ),
        execution_status=required_string(
            data.get("execution_status", "unknown"), field="execution_status"
        ),
        side_effect_classification=side_effect,
        authorization_decision=authorization,
        captured_at=parse_time(data.get("captured_at")),
        metadata=metadata_without_payload(
            data, exclude={"input", "output", "captured_at"}
        ),
    )
    return capture_contract(contract)


def capture_langchain_retriever_event(
    event: Mapping[str, Any],
) -> ContractCaptureResult:
    """Map a LangChain retriever callback event into retrieval evidence."""
    data = dict(event)
    contract = RetrievalEvidenceContract(
        contract_version="langchain.retrieval.v1",
        producer_id=required_string(
            data.get("producer_id", "langchain"), field="producer_id"
        ),
        run_id=required_string(data.get("run_id"), field="run_id"),
        corpus_identity=required_string(
            data.get("corpus_identity"), field="corpus_identity"
        ),
        corpus_digest=optional_string(data.get("corpus_digest")),
        corpus_snapshot_id=optional_string(data.get("corpus_snapshot_id")),
        query_digest=digest_json(
            json_object_from_mapping(data.get("query", {}), field="query")
        ),
        retrieved_item_ids=tuple(
            str(item) for item in data.get("retrieved_item_ids", ())
        ),
        chunk_digests=tuple(str(item) for item in data.get("chunk_digests", ())),
        ranking_metadata=json_object_from_mapping(
            data.get("ranking_metadata", {}), field="ranking_metadata"
        ),
        citation_boundary=required_string(
            data.get("citation_boundary", "not-recorded-by-producer"),
            field="citation_boundary",
        ),
        captured_at=parse_time(data.get("captured_at")),
        metadata=metadata_without_payload(
            data, exclude={"query", "ranking_metadata", "captured_at"}
        ),
    )
    return capture_contract(contract)
