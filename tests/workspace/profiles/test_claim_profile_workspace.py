from datetime import UTC, datetime

from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.services.reliability_claim_profile_service import (
    evaluate_claim_profile,
    get_builtin_claim_profile,
    write_claim_profile_evaluation,
)
from statewake.workspace.models import WorkspaceRecordQuery
from statewake.workspace.workspace import StateWakeWorkspace

_DIGEST = "a" * 64


def _reference(
    kind: str, identity: str, source: str | None = None
) -> EvidenceReference:
    return EvidenceReference(kind, identity, _DIGEST, source or f"{identity}.json")


def _claim_chain() -> ReliabilityEvidenceChain:
    contract_types = (
        "prompt_evidence",
        "model_invocation",
        "retrieval_evidence",
        "policy_evidence",
        "human_approval",
        "tool_call",
        "runtime_trace",
        "evaluator_evidence",
    )
    evidence = tuple(
        _reference(
            "evidence",
            f"ai-contract:{contract_type}:run-1:1",
            f"statewake.ai_contracts.{contract_type}",
        )
        for contract_type in contract_types
    )
    return ReliabilityEvidenceChain(
        chain_id="c1",
        run=_reference("run", "run-1"),
        state=_reference("state", "state-1"),
        evidence=evidence,
        provenance=_reference("provenance", "p1"),
        integrity=_reference("integrity", "i1"),
        verification_status="verified",
        reliability_state="reliable",
        reconciliation_state="verified",
        decision="accept",
        decision_rationale=("bounded claim",),
    )


def test_profile_result_round_trips_through_workspace(tmp_path):
    workspace = StateWakeWorkspace.open(tmp_path / "statewake")
    profile = get_builtin_claim_profile("rag_answer_verified.v1")
    result = evaluate_claim_profile(_claim_chain(), profile)
    result_path = tmp_path / "profile-result.json"
    write_claim_profile_evaluation(result, result_path)

    record = workspace.ingest_file(
        result_path,
        producer_type="statewake-profile-evaluation",
        producer_id="statewake.phase2",
        captured_at=datetime(2026, 9, 21, 0, 0, 0, tzinfo=UTC),
        source_event_id="profile-result-1",
        run_id="run-1",
        metadata={
            "profile_id": result.profile_id,
            "decision": result.decision,
        },
    )

    workspace.verify(record)
    page = workspace.query(WorkspaceRecordQuery(run_id="run-1", limit=10))
    assert len(page.records) == 1
    assert page.records[0].metadata["profile_id"] == "rag_answer_verified.v1"
    assert page.records[0].metadata["decision"] == "accepted"
