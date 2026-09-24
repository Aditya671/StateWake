"""Regression tests for Phase 5 producer integrations."""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from textwrap import dedent

from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.integrations import (
    capture_cicd_release_event,
    capture_cicd_test_result,
    capture_evaluator_result,
    capture_genai_model_invocation,
    capture_genai_runtime_trace,
    capture_langchain_retriever_event,
    capture_langchain_tool_event,
    capture_llamaindex_retrieval_event,
    capture_openai_agent_model_event,
    capture_openai_agent_tool_event,
    capture_openai_agent_trace,
    profile_evidence_reference,
)
from statewake.services.reliability_claim_profile_service import (
    evaluate_claim_profile,
    get_builtin_claim_profile,
)

_NOW = datetime(2026, 9, 21, 0, 0, 0, tzinfo=UTC)
_DIGEST = "0" * 64


def _ref(kind: str, identity: str = "ref") -> EvidenceReference:
    return EvidenceReference(
        kind=kind, identity=identity, digest=_DIGEST, source="test"
    )


def _ai_ref(result: object) -> EvidenceReference:
    return profile_evidence_reference(result)  # type: ignore[arg-type]


def _chain(
    *evidence: EvidenceReference, decision: str = "accept"
) -> ReliabilityEvidenceChain:
    return ReliabilityEvidenceChain(
        chain_id="chain-1",
        run=_ref("run", "run-1"),
        state=_ref("state", "state-1"),
        evidence=evidence,
        provenance=_ref("provenance", "prov-1"),
        integrity=_ref("integrity", "integrity-1"),
        verification_status="verified",
        reliability_state="reliable",
        reconciliation_state="verified",
        decision=decision,
        decision_rationale=("covered by Phase 5 integration evidence",),
    )


def test_core_import_does_not_import_optional_frameworks() -> None:
    """Importing StateWake integrations must not eagerly load optional frameworks."""

    code = dedent("""
    import sys

    import statewake.integrations

    optional_frameworks = (
        "langchain",
        "llama_index",
        "langgraph",
        "openai_agents",
    )

    violations = [
        module_name
        for module_name in optional_frameworks
        if module_name in sys.modules
    ]

    if violations:
        raise SystemExit(
            "Optional frameworks imported eagerly: "
            + ", ".join(violations)
        )
    """)

    subprocess.run(
        [sys.executable, "-c", code],
        check=True,
    )


def test_opentelemetry_span_maps_to_runtime_trace_contract() -> None:
    result = capture_genai_runtime_trace(
        {
            "attributes": {
                "statewake.run_id": "run-otel",
                "trace_id": "trace-1",
                "span_id": "span-1",
                "gen_ai.operation.name": "chat",
                "start_time": _NOW,
                "end_time": _NOW,
                "captured_at": _NOW,
            }
        }
    )
    assert result.payload["contract_type"] == "runtime_trace"
    assert result.payload["framework"] == "opentelemetry-genai"
    assert result.evidence.evidence_id.startswith("ai-contract:runtime_trace:run-otel")


def test_opentelemetry_model_event_maps_to_model_contract() -> None:
    result = capture_genai_model_invocation(
        {
            "attributes": {
                "statewake.run_id": "run-otel",
                "gen_ai.system": "openai",
                "gen_ai.request.model": "gpt-test",
                "parameters": {"temperature": 0},
                "request": {"digest_only": "request"},
                "response": {"digest_only": "response"},
                "captured_at": _NOW,
            }
        }
    )
    assert result.payload["contract_type"] == "model_invocation"
    assert result.payload["provider"] == "openai"
    assert result.payload["request_digest"] != result.payload["response_digest"]


def test_langchain_tool_event_maps_to_tool_call_contract() -> None:
    result = capture_langchain_tool_event(
        {
            "run_id": "run-lc",
            "tool_name": "lookup",
            "input": {"query": "x"},
            "output": {"answer": "y"},
            "execution_status": "success",
            "side_effect_classification": "none",
            "captured_at": _NOW,
        }
    )
    assert result.payload["contract_type"] == "tool_call"
    assert result.payload["tool_name"] == "lookup"


def test_llamaindex_retrieval_event_maps_to_retrieval_contract() -> None:
    result = capture_llamaindex_retrieval_event(
        {
            "run_id": "run-li",
            "corpus_identity": "kb-v1",
            "corpus_snapshot_id": "snap-1",
            "query": {"text": "question"},
            "retrieved_item_ids": ["doc-1"],
            "chunk_digests": [_DIGEST],
            "captured_at": _NOW,
        }
    )
    assert result.payload["contract_type"] == "retrieval"
    assert result.payload["corpus_snapshot_id"] == "snap-1"


def test_openai_agents_trace_maps_model_and_tool_events() -> None:
    trace = capture_openai_agent_trace(
        {
            "run_id": "run-agent",
            "trace_id": "trace-agent",
            "span_id": "span-agent",
            "start_time": _NOW,
            "end_time": _NOW,
            "captured_at": _NOW,
        }
    )
    model = capture_openai_agent_model_event(
        {
            "run_id": "run-agent",
            "model_name": "gpt-test",
            "parameters": {},
            "request": {"prompt_digest": "abc"},
            "response": {"response_digest": "def"},
            "captured_at": _NOW,
        }
    )
    tool = capture_openai_agent_tool_event(
        {
            "run_id": "run-agent",
            "tool_name": "search",
            "input": {"q": "statewake"},
            "output": {"ids": ["1"]},
            "execution_status": "success",
            "side_effect_classification": "none",
            "captured_at": _NOW,
        }
    )
    assert trace.payload["contract_type"] == "runtime_trace"
    assert model.payload["contract_type"] == "model_invocation"
    assert tool.payload["contract_type"] == "tool_call"


def test_adapter_output_can_be_profile_evaluated() -> None:
    retrieval = capture_langchain_retriever_event(
        {
            "run_id": "run-rag",
            "corpus_identity": "kb-v1",
            "corpus_digest": _DIGEST,
            "query": {"text": "what changed"},
            "retrieved_item_ids": ["doc-1"],
            "chunk_digests": [_DIGEST],
            "citation_boundary": "answer-citations",
            "captured_at": _NOW,
        }
    )
    profile = get_builtin_claim_profile("rag_answer_verified.v1")
    model = capture_openai_agent_model_event(
        {
            "run_id": "run-rag",
            "model_name": "gpt-test",
            "parameters": {},
            "request": {"prompt": "digest-only"},
            "response": {"answer": "digest-only"},
            "captured_at": _NOW,
        }
    )
    prompt = EvidenceReference(
        kind="ai-contract:prompt_evidence",
        identity="ai-contract:prompt:run-rag",
        digest=_DIGEST,
        source="statewake.ai_contracts.prompt",
    )
    result = evaluate_claim_profile(
        _chain(prompt, _ai_ref(model), _ai_ref(retrieval)), profile
    )
    assert result.decision == "accepted"


def test_cicd_and_evaluator_integrations_emit_phase1_contracts() -> None:
    release = capture_cicd_release_event(
        {
            "producer_id": "github-actions",
            "run_id": "run-ci",
            "policy_id": "release-gate",
            "policy_version": "1",
            "decision": "allow-with-limitations",
            "rationale": {"tests": "pass"},
            "captured_at": _NOW,
        }
    )
    ci_tests = capture_cicd_test_result(
        {
            "producer_id": "github-actions",
            "run_id": "run-ci",
            "job_name": "unit-tests",
            "metric_values": {"passed": 10, "failed": 0},
            "thresholds": {"failed": 0},
            "captured_at": _NOW,
        }
    )
    evaluator = capture_evaluator_result(
        {
            "producer_id": "eval-system",
            "run_id": "run-eval",
            "evaluator_id": "faithfulness",
            "evaluator_version": "1",
            "metric_version": "1",
            "metric_values": {"score": 1.0},
            "thresholds": {"score": 0.8},
            "dataset_identity": "fixture-set",
            "evaluator_limitations": "deterministic fixture only",
            "captured_at": _NOW,
        }
    )
    assert release.payload["contract_type"] == "policy"
    assert ci_tests.payload["contract_type"] == "evaluator"
    assert evaluator.payload["contract_type"] == "evaluator"
