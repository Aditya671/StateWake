"""Generic evaluator-result integration for external evaluation systems."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from statewake.ai_contracts.evaluator import EvaluatorEvidenceContract

from .base import (
    ContractCaptureResult,
    capture_contract,
    json_object_from_mapping,
    metadata_without_payload,
    parse_time,
    required_string,
)


def capture_evaluator_result(event: Mapping[str, Any]) -> ContractCaptureResult:
    """Map a framework-neutral evaluator result into evaluator evidence."""
    data = dict(event)
    contract = EvaluatorEvidenceContract(
        contract_version="external.evaluator.v1",
        producer_id=required_string(data.get("producer_id"), field="producer_id"),
        run_id=required_string(data.get("run_id"), field="run_id"),
        evaluator_id=required_string(data.get("evaluator_id"), field="evaluator_id"),
        evaluator_version=required_string(
            data.get("evaluator_version"), field="evaluator_version"
        ),
        metric_version=required_string(
            data.get("metric_version"), field="metric_version"
        ),
        metric_values=json_object_from_mapping(
            data.get("metric_values", {}), field="metric_values"
        ),
        thresholds=json_object_from_mapping(
            data.get("thresholds", {}), field="thresholds"
        ),
        dataset_identity=required_string(
            data.get("dataset_identity"), field="dataset_identity"
        ),
        evaluator_limitations=required_string(
            data.get("evaluator_limitations"), field="evaluator_limitations"
        ),
        captured_at=parse_time(data.get("captured_at")),
        metadata=metadata_without_payload(
            data, exclude={"metric_values", "thresholds", "captured_at"}
        ),
    )
    return capture_contract(contract)
