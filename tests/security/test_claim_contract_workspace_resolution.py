"""Profile content verification must reject fabricated and corrupted references."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from statewake.domain.reliability_claim_profile import ReliabilityClaimProfile
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.integrations import (
    capture_llamaindex_retrieval_event,
    profile_evidence_reference,
)
from statewake.services.reliability_claim_profile_service import (
    evaluate_claim_profile,
    evaluate_claim_profile_with_workspace,
)
from statewake.workspace import StateWakeWorkspace


def _chain(reference: EvidenceReference) -> ReliabilityEvidenceChain:
    marker = "0" * 64

    def ref(kind: str) -> EvidenceReference:
        return EvidenceReference(kind=kind, identity=f"test:{kind}", digest=marker)

    return ReliabilityEvidenceChain(
        chain_id="resolution-test",
        run=ref("run"),
        state=ref("state"),
        evidence=(reference,),
        provenance=ref("provenance"),
        integrity=ref("integrity"),
        verification_status="verified",
        reliability_state="reliable",
        reconciliation_state="verified",
        decision="accept",
        decision_rationale=("fixture",),
    )


def _profile() -> ReliabilityClaimProfile:
    return ReliabilityClaimProfile(
        profile_id="retrieval-check",
        version="1",
        title="retrieval check",
        required_evidence_kinds=("run", "state", "provenance", "integrity"),
        required_verification_conditions=("chain_verified",),
        allowed_decisions=("accept",),
        required_ai_contract_types=("retrieval_evidence",),
    )


def test_workspace_resolution_rejects_fabricated_but_structurally_valid_reference(
    tmp_path: Path,
) -> None:
    workspace = StateWakeWorkspace.open(tmp_path / "statewake")
    fake = EvidenceReference(
        kind="ai-contract:retrieval_evidence",
        identity="ai-contract:retrieval:run-1:fake",
        digest="0" * 64,
    )
    chain = _chain(fake)
    assert evaluate_claim_profile(chain, _profile()).satisfied
    result = evaluate_claim_profile_with_workspace(chain, _profile(), workspace)
    assert result.satisfied is False
    assert "resolved-ai-contract:retrieval_evidence" in result.failed_conditions


def test_workspace_resolution_accepts_persisted_verified_contract(
    tmp_path: Path,
) -> None:
    workspace = StateWakeWorkspace.open(tmp_path / "statewake")
    event = capture_llamaindex_retrieval_event(
        {
            "run_id": "run-1",
            "corpus_identity": "kb-v1",
            "corpus_snapshot_id": "s-1",
            "query": {"text": "q"},
            "retrieved_item_ids": ["doc-1"],
            "chunk_digests": ["0" * 64],
            "captured_at": datetime(2026, 9, 23, tzinfo=UTC),
        }
    )
    record = event.persist(workspace)
    chain = _chain(profile_evidence_reference(event))
    assert evaluate_claim_profile_with_workspace(chain, _profile(), workspace).satisfied
    path = (
        workspace.configuration.artifact_root
        / record.artifact_digest[:2]
        / record.artifact_digest[2:]
    )
    path.write_bytes(b"modified evidence")
    assert not evaluate_claim_profile_with_workspace(
        chain, _profile(), workspace
    ).satisfied
