"""LangGraph run and checkpoint mapping into runtime trace evidence."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from statewake.ai_contracts.runtime import RuntimeTraceContract

from .base import (
    ContractCaptureResult,
    capture_contract,
    metadata_without_payload,
    optional_string,
    parse_time,
    required_observed_time,
    required_string,
)


def capture_langgraph_run_event(event: Mapping[str, Any]) -> ContractCaptureResult:
    """Map a LangGraph run/node/checkpoint event into runtime trace evidence."""
    data = dict(event)
    contract = RuntimeTraceContract(
        contract_version="langgraph.runtime.v1",
        producer_id=required_string(
            data.get("producer_id", "langgraph"), field="producer_id"
        ),
        run_id=required_string(data.get("run_id"), field="run_id"),
        framework="langgraph",
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
