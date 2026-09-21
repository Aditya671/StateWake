"""Deterministic claim-profile validation over an existing evidence chain."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from statewake.utils.json_support import load_object

from ..domain.reliability_claim_profile import ReliabilityClaimProfile
from ..domain.reliability_evidence import EvidenceReference, ReliabilityEvidenceChain
from ..services.persistence import atomic_write_text

_PROFILE_EVALUATION_FORMAT_VERSION = "1"
_AI_CONTRACT_PREFIX = "ai-contract:"


@dataclass(frozen=True, slots=True)
class ClaimProfileEvaluation:
    """Explainable result of applying a claim profile to a chain."""

    profile_id: str
    profile_version: str
    satisfied: bool
    passed_conditions: tuple[str, ...]
    failed_conditions: tuple[str, ...]
    allowed_decisions: tuple[str, ...]
    decision: str
    passed_requirements: tuple[str, ...]
    failed_requirements: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    caveats: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Serialize this evaluation for reports, workspace records, and tests."""
        return {
            "format_version": _PROFILE_EVALUATION_FORMAT_VERSION,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "satisfied": self.satisfied,
            "decision": self.decision,
            "passed_conditions": list(self.passed_conditions),
            "failed_conditions": list(self.failed_conditions),
            "allowed_decisions": list(self.allowed_decisions),
            "passed_requirements": list(self.passed_requirements),
            "failed_requirements": list(self.failed_requirements),
            "missing_evidence": list(self.missing_evidence),
            "caveats": list(self.caveats),
        }


class ClaimProfileRegistry:
    """Version-aware registry for built-in and user-supplied claim profiles."""

    def __init__(self, profiles: tuple[ReliabilityClaimProfile, ...]) -> None:
        """Create a registry after rejecting ambiguous profile identities."""
        by_key: dict[tuple[str, str], ReliabilityClaimProfile] = {}
        for profile in profiles:
            key = (profile.profile_id, profile.version)
            if key in by_key:
                raise ValueError(
                    f"duplicate claim profile id/version: {profile.profile_id}@"
                    f"{profile.version}"
                )
            by_key[key] = profile
        self._profiles = tuple(profiles)
        self._by_key = by_key

    def list(self) -> tuple[ReliabilityClaimProfile, ...]:
        """Return profiles in deterministic registration order."""
        return self._profiles

    def get(self, profile_id: str, version: str = "1") -> ReliabilityClaimProfile:
        """Return the exact profile identified by id and version."""
        try:
            return self._by_key[(profile_id, version)]
        except KeyError as exc:
            raise KeyError(f"unknown claim profile: {profile_id}@{version}") from exc


def _references(chain: ReliabilityEvidenceChain) -> tuple[EvidenceReference, ...]:
    """Return all concrete references that can satisfy profile requirements."""
    optional = (
        chain.reconciliation_ref,
        chain.recovery_ref,
        chain.attestation_ref,
        chain.decision_basis_ref,
        chain.comparison_ref,
        chain.reconciliation_binding_ref,
    )
    return (
        chain.run,
        chain.state,
        *chain.evidence,
        chain.provenance,
        chain.integrity,
        *(item for item in optional if item is not None),
    )


def _has_kind(chain: ReliabilityEvidenceChain, kind: str) -> bool:
    """Return whether the supplied chain contains the requested kind."""
    return any(reference.kind == kind for reference in _references(chain))


def _reference_matches_ai_contract(
    reference: EvidenceReference,
    contract_type: str,
) -> bool:
    """Return whether one evidence reference points at an AI contract type."""
    direct_kind = f"ai-contract:{contract_type}"
    if reference.kind == direct_kind:
        return True
    if reference.identity.startswith(f"{_AI_CONTRACT_PREFIX}{contract_type}:"):
        return True
    if reference.source and contract_type in reference.source:
        return True
    return False


def _has_ai_contract(chain: ReliabilityEvidenceChain, contract_type: str) -> bool:
    """Return whether the chain contains the required AI contract evidence."""
    return any(
        _reference_matches_ai_contract(reference, contract_type)
        for reference in _references(chain)
    )


def _decision_for(
    *,
    profile: ReliabilityClaimProfile,
    failed: tuple[str, ...],
    chain_decision_allowed: bool,
) -> str:
    """Map structural profile evidence into the roadmap decision vocabulary."""
    if not failed and chain_decision_allowed:
        if profile.profile_id == "ai_decision_with_limitations.v1":
            return "accepted_with_limitations"
        return "accepted"
    if profile.profile_id == "policy_reverification_required.v1":
        return "requires_reverification"
    if "review" in profile.allowed_decisions and profile.caveats:
        return "accepted_with_limitations"
    return "rejected"


def evaluate_claim_profile(
    chain: ReliabilityEvidenceChain, profile: ReliabilityClaimProfile
) -> ClaimProfileEvaluation:
    """Apply declared structural/state conditions; never score model behavior."""
    passed: list[str] = []
    failed: list[str] = []
    missing_evidence: list[str] = []

    for kind in profile.required_evidence_kinds:
        label = f"evidence-kind:{kind}"
        if _has_kind(chain, kind):
            passed.append(label)
        else:
            failed.append(label)
            missing_evidence.append(kind)

    for contract_type in profile.required_ai_contract_types:
        label = f"ai-contract:{contract_type}"
        if _has_ai_contract(chain, contract_type):
            passed.append(label)
        else:
            failed.append(label)
            missing_evidence.append(label)

    for condition in profile.required_verification_conditions:
        ok = {
            "chain_verified": chain.verification_status == "verified",
            "reconciliation_verified": chain.reconciliation_state == "verified",
            "recovery_present": chain.recovery_ref is not None,
            "attestation_present": chain.attestation_ref is not None,
            "decision_rationale_present": bool(chain.decision_rationale),
            "decision_basis_present": chain.decision_basis_ref is not None,
        }.get(condition)
        if ok is True:
            passed.append(condition)
        else:
            failed.append(condition)

    if (
        profile.required_reconciliation_states
        and chain.reconciliation_state not in profile.required_reconciliation_states
    ):
        failed.append(f"reconciliation-state:{chain.reconciliation_state}")
    elif profile.required_reconciliation_states:
        passed.append(f"reconciliation-state:{chain.reconciliation_state}")

    if (
        profile.required_reliability_states
        and chain.reliability_state not in profile.required_reliability_states
    ):
        failed.append(f"reliability-state:{chain.reliability_state}")
    elif profile.required_reliability_states:
        passed.append(f"reliability-state:{chain.reliability_state}")

    if profile.required_rationale:
        if chain.decision_rationale:
            passed.append("rationale-present")
        else:
            failed.append("rationale-present")

    chain_decision_allowed = chain.decision in set(profile.allowed_decisions)
    if not chain_decision_allowed:
        failed.append(f"decision:{chain.decision}")

    failed_tuple = tuple(failed)
    decision = _decision_for(
        profile=profile,
        failed=failed_tuple,
        chain_decision_allowed=chain_decision_allowed,
    )
    return ClaimProfileEvaluation(
        profile_id=profile.profile_id,
        profile_version=profile.version,
        satisfied=not failed_tuple and chain_decision_allowed,
        passed_conditions=tuple(passed),
        failed_conditions=failed_tuple,
        allowed_decisions=profile.allowed_decisions,
        decision=decision,
        passed_requirements=tuple(passed),
        failed_requirements=failed_tuple,
        missing_evidence=tuple(missing_evidence),
        caveats=profile.caveats,
    )


def write_claim_profile(profile: ReliabilityClaimProfile, path: Path) -> None:
    """Persist a reliability claim profile as versioned JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        path, json.dumps(profile.to_dict(), indent=2, sort_keys=True) + "\n"
    )


def write_claim_profile_evaluation(
    evaluation: ClaimProfileEvaluation, path: Path
) -> None:
    """Persist a profile evaluation as deterministic JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        path, json.dumps(evaluation.to_dict(), indent=2, sort_keys=True) + "\n"
    )


def load_claim_profile(path: Path) -> ReliabilityClaimProfile:
    """Load a reliability claim profile from JSON."""
    payload = load_object(path)
    if not isinstance(payload, dict):
        raise ValueError("claim profile root must be an object.")
    return ReliabilityClaimProfile.from_dict(payload)


def _profile(
    *,
    profile_id: str,
    title: str,
    description: str,
    required_ai_contract_types: tuple[str, ...],
    allowed_decisions: tuple[str, ...] = ("accept", "review", "reject"),
    conditions: tuple[str, ...] = (
        "chain_verified",
        "reconciliation_verified",
        "decision_rationale_present",
    ),
    caveats: tuple[str, ...] = (),
    required_evidence_kinds: tuple[str, ...] = (
        "run",
        "state",
        "provenance",
        "integrity",
    ),
    required_reconciliation_states: tuple[str, ...] = ("verified", "recovered"),
    required_reliability_states: tuple[str, ...] = ("reliable", "recovered"),
) -> ReliabilityClaimProfile:
    """Create a built-in AI reliability claim profile."""
    return ReliabilityClaimProfile(
        profile_id=profile_id,
        version="1",
        title=title,
        description=description,
        required_evidence_kinds=required_evidence_kinds,
        required_verification_conditions=conditions,
        allowed_decisions=allowed_decisions,
        required_reconciliation_states=required_reconciliation_states,
        required_reliability_states=required_reliability_states,
        required_ai_contract_types=required_ai_contract_types,
        caveats=caveats,
    )


BUILTIN_CLAIM_PROFILES: tuple[ReliabilityClaimProfile, ...] = (
    _profile(
        profile_id="rag_answer_verified.v1",
        title="RAG answer verified",
        description=(
            "A RAG answer is supported by digest-bound prompt, model, retrieval, "
            "and citation-bound evidence."
        ),
        required_ai_contract_types=(
            "prompt_evidence",
            "model_invocation",
            "retrieval_evidence",
        ),
    ),
    _profile(
        profile_id="tool_action_authorized.v1",
        title="Tool action authorized",
        description=(
            "A tool action was authorized by policy, executed under a known schema, "
            "and recorded with input and output digests."
        ),
        required_ai_contract_types=("tool_call", "policy_evidence"),
    ),
    _profile(
        profile_id="model_invocation_reconstructable.v1",
        title="Model invocation reconstructable",
        description=(
            "A model invocation can be reconstructed from provider, model, "
            "parameters, request/response digests, and runtime trace."
        ),
        required_ai_contract_types=("model_invocation", "runtime_trace"),
    ),
    _profile(
        profile_id="human_approval_recorded.v1",
        title="Human approval recorded",
        description=(
            "A human approval exists with actor reference, role, scope, approval "
            "basis, and time."
        ),
        required_ai_contract_types=("human_approval",),
    ),
    _profile(
        profile_id="incident_recovery_verified.v1",
        title="Incident recovery verified",
        description=(
            "A failure and recovery are separately recorded and the recovered "
            "state is verified."
        ),
        required_ai_contract_types=("runtime_trace",),
        conditions=(
            "chain_verified",
            "reconciliation_verified",
            "recovery_present",
            "decision_rationale_present",
        ),
        required_evidence_kinds=("run", "state", "provenance", "integrity", "recovery"),
    ),
    _profile(
        profile_id="release_evidence_complete.v1",
        title="Release evidence complete",
        description=(
            "A release claim includes package digest, tests, build evidence, "
            "version, changelog, and unresolved limitations."
        ),
        required_ai_contract_types=("policy_evidence", "human_approval"),
        caveats=("Release authorization remains a separate human decision.",),
    ),
    _profile(
        profile_id="ai_decision_with_limitations.v1",
        title="AI decision with limitations",
        description=(
            "A decision is allowed only with visible caveats and residual risk."
        ),
        required_ai_contract_types=("policy_evidence", "evaluator_evidence"),
        allowed_decisions=("review",),
        caveats=("Decision must travel with its caveats and residual risk.",),
    ),
    _profile(
        profile_id="policy_reverification_required.v1",
        title="Policy reverification required",
        description=(
            "Evidence or trust change requires reverification before acceptance."
        ),
        required_ai_contract_types=("policy_evidence",),
        allowed_decisions=("review", "reject"),
        required_reconciliation_states=("stale", "invalid", "missing"),
        required_reliability_states=("degraded", "unreliable"),
        caveats=("Acceptance is blocked until policy evidence is reverified.",),
    ),
)

_BUILTIN_REGISTRY = ClaimProfileRegistry(BUILTIN_CLAIM_PROFILES)


def _legacy_release_evidence_complete_profile() -> ReliabilityClaimProfile:
    """Return the pre-Phase-2 release profile for legacy callers.

    The roadmap's Phase 2 release profile is intentionally stricter and
    requires AI-policy and human-approval contracts. Older public callers used
    the hyphenated id for release-proof and decision-basis flows that predate
    AI contracts, so the alias preserves that behavior without adding a ninth
    built-in profile or weakening ``release_evidence_complete.v1`` itself.
    """
    return ReliabilityClaimProfile(
        profile_id="release_evidence_complete.v1",
        version="1",
        title="Release evidence complete",
        description=(
            "Legacy release-proof compatibility profile requiring the core "
            "reliability evidence chain without requiring Phase 1 AI contracts."
        ),
        required_evidence_kinds=("run", "state", "provenance", "integrity"),
        required_verification_conditions=(
            "chain_verified",
            "reconciliation_verified",
            "decision_rationale_present",
        ),
        allowed_decisions=("accept", "review", "reject"),
        required_reconciliation_states=("verified", "recovered"),
        required_reliability_states=("reliable", "recovered"),
        caveats=("Release authorization remains a separate human decision.",),
    )


def _legacy_policy_reverification_profile() -> ReliabilityClaimProfile:
    """Return the pre-Phase-2 policy-change review compatibility profile."""
    return ReliabilityClaimProfile(
        profile_id="policy_reverification_required.v1",
        version="1",
        title="Policy reverification required",
        description="Legacy policy-change profile for non-AI evidence chains.",
        required_evidence_kinds=("run", "state", "provenance", "integrity"),
        required_verification_conditions=("chain_verified",),
        allowed_decisions=("review", "reject"),
        caveats=("Acceptance is blocked until policy evidence is reverified.",),
    )


_LEGACY_PROFILE_OBJECTS = {
    "release-evidence-complete": _legacy_release_evidence_complete_profile,
    "compliance-handoff-ready": _legacy_release_evidence_complete_profile,
    "model-prompt-change-review": _legacy_policy_reverification_profile,
}
_LEGACY_PROFILE_ALIASES = {
    "incident-recovery-verified": "incident_recovery_verified.v1",
}


def list_builtin_claim_profiles() -> tuple[ReliabilityClaimProfile, ...]:
    """Return all built-in claim profiles in deterministic order."""
    return _BUILTIN_REGISTRY.list()


def get_builtin_claim_profile(
    profile_id: str, version: str = "1"
) -> ReliabilityClaimProfile:
    """Return a built-in reliability claim profile by identifier."""
    legacy_factory = _LEGACY_PROFILE_OBJECTS.get(profile_id)
    if legacy_factory is not None:
        profile = legacy_factory()
        if profile.version != version:
            raise KeyError(f"unknown claim profile: {profile_id}@{version}")
        return profile
    canonical_profile_id = _LEGACY_PROFILE_ALIASES.get(profile_id, profile_id)
    return _BUILTIN_REGISTRY.get(canonical_profile_id, version)
