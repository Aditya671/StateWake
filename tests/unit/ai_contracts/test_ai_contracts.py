"""Regression tests for AI evidence contracts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from statewake.ai_contracts import (
    EvaluatorEvidenceContract,
    HumanApprovalContract,
    ModelInvocationContract,
    PromptEvidenceContract,
    RetrievalEvidenceContract,
    RuntimeTraceContract,
    ToolCallContract,
    contract_digest,
    contract_from_json_bytes,
    contract_to_json_bytes,
    validate_contract_payload,
)

NOW = datetime(2026, 9, 21, 0, 0, tzinfo=UTC)


def test_prompt_contract_requires_template_or_rendered_digest() -> None:
    """Prevent unverifiable prompt evidence."""
    with pytest.raises(
        ValueError, match="prompt_template_id or rendered_prompt_digest"
    ):
        PromptEvidenceContract(
            contract_version="1",
            producer_id="producer",
            run_id="run-1",
            source="prompt-builder",
            captured_at=NOW,
        )


def test_model_contract_rejects_naive_datetime() -> None:
    """Prevent ambiguous model invocation timestamps."""
    with pytest.raises(ValueError, match="timezone-aware"):
        ModelInvocationContract(
            contract_version="1",
            producer_id="producer",
            run_id="run-1",
            provider="openai",
            model_name="example-model",
            model_version="snapshot-1",
            parameters={"temperature": 0},
            request_digest="req",
            response_digest="res",
            captured_at=datetime(2026, 9, 21, 0, 0),  # noqa: DTZ001
        )


def test_model_contract_requires_omission_reason_for_missing_version() -> None:
    """Keep model-version gaps explicit instead of silently accepted."""
    with pytest.raises(ValueError, match="model_version requires an omission reason"):
        ModelInvocationContract(
            contract_version="1",
            producer_id="producer",
            run_id="run-1",
            provider="openai",
            model_name="example-model",
            parameters={"temperature": 0},
            request_digest="req",
            response_digest="res",
            captured_at=NOW,
        )


def test_tool_call_contract_requires_authorization_for_side_effects() -> None:
    """Prevent side-effecting tool evidence from looking complete without authorization."""
    with pytest.raises(ValueError, match="authorization_decision"):
        ToolCallContract(
            contract_version="1",
            producer_id="producer",
            run_id="run-1",
            tool_name="send_email",
            schema_version="schema-v1",
            input_digest="input",
            output_digest="output",
            execution_status="succeeded",
            side_effect_classification="external_write",
            captured_at=NOW,
        )


def test_retrieval_contract_requires_corpus_snapshot_or_digest() -> None:
    """Prevent RAG claims without retrievable corpus identity."""
    with pytest.raises(ValueError, match="corpus_digest or corpus_snapshot_id"):
        RetrievalEvidenceContract(
            contract_version="1",
            producer_id="producer",
            run_id="run-1",
            corpus_identity="kb",
            query_digest="query",
            retrieved_item_ids=("doc-1",),
            chunk_digests=("chunk-1",),
            citation_boundary="paragraph",
            captured_at=NOW,
        )


def test_evaluator_contract_preserves_threshold_and_metric_version() -> None:
    """Prevent score-only evaluation evidence."""
    contract = EvaluatorEvidenceContract(
        contract_version="1",
        producer_id="producer",
        run_id="run-1",
        evaluator_id="faithfulness",
        evaluator_version="2.0",
        metric_version="faithfulness-v1",
        metric_values={"score": 0.92},
        thresholds={"min_score": 0.85},
        dataset_identity="fixture-set-v1",
        evaluator_limitations="deterministic fixture only",
        captured_at=NOW,
    )
    payload = contract.to_dict()
    assert payload["metric_version"] == "faithfulness-v1"
    assert payload["thresholds"] == {"min_score": 0.85}


def test_human_approval_contract_requires_scope() -> None:
    """Prevent approval records from becoming globally ambiguous."""
    with pytest.raises(ValueError, match="scope"):
        HumanApprovalContract(
            contract_version="1",
            producer_id="producer",
            run_id="run-1",
            actor_identity_ref="user:reviewer-1",
            role="risk-owner",
            approval_action="approved_with_limitations",
            approval_basis_digest="basis",
            scope=" ",
            captured_at=NOW,
        )


def test_runtime_trace_contract_links_retry_and_recovery() -> None:
    """Prevent successful retry evidence from erasing failure history."""
    contract = RuntimeTraceContract(
        contract_version="1",
        producer_id="producer",
        run_id="run-2",
        framework="langgraph",
        trace_id="trace-1",
        span_id="span-2",
        retry_of_run_id="run-1",
        recovery_run_id="run-3",
        started_at=NOW,
        ended_at=NOW + timedelta(seconds=1),
        error_status="recovered",
        captured_at=NOW + timedelta(seconds=2),
    )
    payload = contract.to_dict()
    assert payload["retry_of_run_id"] == "run-1"
    assert payload["recovery_run_id"] == "run-3"


def test_contract_serialization_is_deterministic() -> None:
    """Prevent digest drift for equivalent contract payloads."""
    first = PromptEvidenceContract(
        contract_version="1",
        producer_id="producer",
        run_id="run-1",
        source="prompt-builder",
        prompt_template_id="template-1",
        rendered_prompt_digest="rendered",
        captured_at=NOW,
        metadata={"b": 2, "a": 1},
    ).to_dict()
    second = PromptEvidenceContract(
        contract_version="1",
        producer_id="producer",
        run_id="run-1",
        source="prompt-builder",
        prompt_template_id="template-1",
        rendered_prompt_digest="rendered",
        captured_at=NOW,
        metadata={"a": 1, "b": 2},
    ).to_dict()
    assert contract_to_json_bytes(first) == contract_to_json_bytes(second)
    assert contract_digest(first) == contract_digest(second)


def test_contract_to_evidence_reference_round_trip() -> None:
    """Prove integration with the existing evidence model."""
    contract = ToolCallContract(
        contract_version="1",
        producer_id="producer",
        run_id="run-1",
        tool_name="lookup",
        schema_version="schema-v1",
        input_digest="input",
        output_digest="output",
        authorization_decision=None,
        execution_status="succeeded",
        side_effect_classification="none",
        captured_at=NOW,
    )
    item = contract.to_evidence_item()
    restored = type(item).from_dict(item.to_dict())
    assert restored.digest == item.digest
    assert restored.metadata["contract_type"] == "tool_call"


def test_serialized_contract_payload_common_validation() -> None:
    """Validate serialized contract boundaries independently from Python objects."""
    contract = PromptEvidenceContract(
        contract_version="1",
        producer_id="producer",
        run_id="run-1",
        source="prompt-builder",
        rendered_prompt_digest="rendered",
        captured_at=NOW,
    )
    loaded = contract_from_json_bytes(contract_to_json_bytes(contract.to_dict()))
    validate_contract_payload(loaded)
