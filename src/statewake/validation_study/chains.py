"""Fixture-backed reliability chains for Phase 7 validation cases."""

from __future__ import annotations

from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.validation_study.model import WorkloadKind, canonical_digest


def _digest(seed: str) -> str:
    """Return a deterministic digest for a fixture seed."""
    return canonical_digest({"seed": seed})


def _ref(kind: str, identity: str) -> EvidenceReference:
    """Return a deterministic evidence reference."""
    return EvidenceReference(
        kind=kind, identity=identity, digest=_digest(f"{kind}:{identity}")
    )


def _contract(contract_type: str, workload: WorkloadKind) -> EvidenceReference:
    """Return a reference shaped like a Phase 1 AI contract."""
    identity = f"ai-contract:{contract_type}:{workload}:fixture"
    return EvidenceReference(
        kind="evidence",
        identity=identity,
        digest=_digest(identity),
        source=f"statewake.ai_contracts.{contract_type}",
    )


def chain_for_workload(
    workload: WorkloadKind,
    *,
    omit_contracts: tuple[str, ...] = (),
    verified: bool = True,
    preserve_failure: bool = True,
) -> ReliabilityEvidenceChain:
    """Build a deterministic StateWake evidence chain for one workload."""
    required_contracts = {
        "rag_answer": ("prompt_evidence", "model_invocation", "retrieval_evidence"),
        "tool_action": ("tool_call", "policy_evidence"),
        "incident_recovery": ("runtime_trace",),
        "release_verification": ("policy_evidence", "human_approval"),
        "human_approval_workflow": ("human_approval",),
    }[workload]
    evidence = tuple(
        _contract(contract_type, workload)
        for contract_type in required_contracts
        if contract_type not in set(omit_contracts)
    )
    extra: tuple[EvidenceReference, ...] = (_ref("evidence", f"{workload}:summary"),)
    if workload == "release_verification":
        extra = (_ref("release-trust", f"{workload}:bundle"),)
    if extra:
        evidence = (*evidence, *extra)
    return ReliabilityEvidenceChain(
        chain_id=f"phase7:{workload}",
        run=_ref("run", f"{workload}:run"),
        state=_ref("state", f"{workload}:state"),
        evidence=evidence,
        provenance=_ref("provenance", f"{workload}:provenance"),
        integrity=_ref("integrity", f"{workload}:integrity"),
        verification_status="verified" if verified else "failed",
        reliability_state="recovered"
        if workload == "incident_recovery"
        else "reliable",
        reconciliation_state="verified" if verified else "invalid",
        reconciliation_ref=_ref("reconciliation", f"{workload}:reconciliation"),
        recovery_ref=_ref("recovery", f"{workload}:recovery")
        if workload == "incident_recovery" and preserve_failure
        else None,
        attestation_ref=_ref("attestation", f"{workload}:attestation"),
        decision_basis_ref=_ref("decision-basis", f"{workload}:basis"),
        # Fault injection must create a *valid* rejected/reviewable chain.
        # An invalid accepted chain raises during construction, before the
        # verifier has any opportunity to observe the injected fault.
        decision="accept" if verified else "review",
        decision_rationale=(f"fixture rationale for {workload}",),
    )
