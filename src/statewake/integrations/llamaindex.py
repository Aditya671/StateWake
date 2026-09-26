"""LlamaIndex event mapping into StateWake retrieval and evaluator contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from statewake.ai_contracts.evaluator import EvaluatorEvidenceContract
from statewake.ai_contracts.retrieval import RetrievalEvidenceContract

from .base import (
    ContractCaptureResult,
    capture_contract,
    digest_json,
    json_object_from_mapping,
    metadata_without_payload,
    optional_string,
    parse_time,
    required_observed_mapping,
    required_string,
)


def capture_llamaindex_retrieval_event(
    event: Mapping[str, Any],
) -> ContractCaptureResult:
    """Map a LlamaIndex retrieval event into retrieval evidence."""
    data = dict(event)
    contract = RetrievalEvidenceContract(
        contract_version="llamaindex.retrieval.v1",
        producer_id=required_string(
            data.get("producer_id", "llamaindex"), field="producer_id"
        ),
        run_id=required_string(data.get("run_id"), field="run_id"),
        corpus_identity=required_string(
            data.get("corpus_identity"), field="corpus_identity"
        ),
        corpus_digest=optional_string(data.get("corpus_digest")),
        corpus_snapshot_id=optional_string(data.get("corpus_snapshot_id")),
        query_digest=digest_json(required_observed_mapping(data, field="query")),
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


def capture_llamaindex_evaluator_event(
    event: Mapping[str, Any],
) -> ContractCaptureResult:
    """Map a LlamaIndex evaluator event into evaluator evidence."""
    data = dict(event)
    contract = EvaluatorEvidenceContract(
        contract_version="llamaindex.evaluator.v1",
        producer_id=required_string(
            data.get("producer_id", "llamaindex"), field="producer_id"
        ),
        run_id=required_string(data.get("run_id"), field="run_id"),
        evaluator_id=required_string(data.get("evaluator_id"), field="evaluator_id"),
        evaluator_version=required_string(
            data.get("evaluator_version", "unknown"), field="evaluator_version"
        ),
        metric_version=required_string(
            data.get("metric_version", "llamaindex-eval.v1"), field="metric_version"
        ),
        metric_values=json_object_from_mapping(
            data.get("metric_values", {}), field="metric_values"
        ),
        thresholds=json_object_from_mapping(
            data.get("thresholds", {"recorded": True}), field="thresholds"
        ),
        dataset_identity=required_string(
            data.get("dataset_identity", "llamaindex-sample"), field="dataset_identity"
        ),
        evaluator_limitations=required_string(
            data.get("evaluator_limitations", "LlamaIndex evaluator output only."),
            field="evaluator_limitations",
        ),
        captured_at=parse_time(data.get("captured_at")),
        metadata=metadata_without_payload(
            data, exclude={"metric_values", "thresholds", "captured_at"}
        ),
    )
    return capture_contract(contract)
