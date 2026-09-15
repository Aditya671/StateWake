"""Deterministic claim-profile validation over an existing evidence chain."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from statewake.utils.json_support import load_object

from ..domain.reliability_claim_profile import ReliabilityClaimProfile
from ..domain.reliability_evidence import ReliabilityEvidenceChain
from ..services.persistence import atomic_write_text


@dataclass(frozen=True, slots=True)
class ClaimProfileEvaluation:
    """Explainable result of applying a claim profile to a chain."""

    profile_id: str
    profile_version: str
    satisfied: bool
    passed_conditions: tuple[str, ...]
    failed_conditions: tuple[str, ...]
    allowed_decisions: tuple[str, ...]


def _has_kind(chain: ReliabilityEvidenceChain, kind: str) -> bool:
    """Return whether the supplied collection contains the requested kind."""
    references = (
        chain.run,
        chain.state,
        *chain.evidence,
        chain.provenance,
        chain.integrity,
        chain.reconciliation_ref,
        chain.recovery_ref,
        chain.attestation_ref,
    )
    return any(
        reference is not None and reference.kind == kind for reference in references
    )


def evaluate_claim_profile(
    chain: ReliabilityEvidenceChain, profile: ReliabilityClaimProfile
) -> ClaimProfileEvaluation:
    """Apply only declared structural/state conditions; never score model behavior."""
    passed: list[str] = []
    failed: list[str] = []
    for kind in profile.required_evidence_kinds:
        label = f"evidence-kind:{kind}"
        (passed if _has_kind(chain, kind) else failed).append(label)
    for condition in profile.required_verification_conditions:
        ok = {
            "chain_verified": chain.verification_status == "verified",
            "reconciliation_verified": chain.reconciliation_state == "verified",
            "recovery_present": chain.recovery_ref is not None,
            "attestation_present": chain.attestation_ref is not None,
            "decision_rationale_present": bool(chain.decision_rationale),
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
    return ClaimProfileEvaluation(
        profile_id=profile.profile_id,
        profile_version=profile.version,
        satisfied=not failed and chain.decision in set(profile.allowed_decisions),
        passed_conditions=tuple(passed),
        failed_conditions=tuple(failed),
        allowed_decisions=profile.allowed_decisions,
    )


def write_claim_profile(profile: ReliabilityClaimProfile, path: Path) -> None:
    """Persist a reliability claim profile as versioned JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        path, json.dumps(profile.to_dict(), indent=2, sort_keys=True) + "\n"
    )


def load_claim_profile(path: Path) -> ReliabilityClaimProfile:
    """Load a reliability claim profile from JSON."""
    payload = load_object(path)
    if not isinstance(payload, dict):
        raise ValueError("claim profile root must be an object.")
    return ReliabilityClaimProfile.from_dict(payload)


BUILTIN_CLAIM_PROFILES: tuple[ReliabilityClaimProfile, ...] = (
    ReliabilityClaimProfile(
        profile_id="release-evidence-complete",
        version="1",
        title="Release evidence complete",
        description="""
        Evidence and verification conditions for a bounded release decision.
        """,
        required_evidence_kinds=("run", "state", "evidence", "provenance", "integrity"),
        required_verification_conditions=(
            "chain_verified",
            "reconciliation_verified",
            "decision_rationale_present",
        ),
        allowed_decisions=("accept", "review", "reject"),
        required_reliability_states=("reliable", "recovered"),
    ),
    ReliabilityClaimProfile(
        profile_id="incident-recovery-verified",
        version="1",
        title="Incident recovery verified",
        description="Evidence conditions for a verified recovery outcome.",
        required_evidence_kinds=(
            "run",
            "state",
            "evidence",
            "provenance",
            "integrity",
            "recovery",
        ),
        required_verification_conditions=(
            "chain_verified",
            "reconciliation_verified",
            "recovery_present",
            "decision_rationale_present",
        ),
        allowed_decisions=("accept", "review"),
        required_reconciliation_states=("verified", "recovered"),
        required_reliability_states=("recovered", "reliable"),
    ),
    ReliabilityClaimProfile(
        profile_id="model-prompt-change-review",
        version="1",
        title="Model/prompt change requires review",
        description="""
        A bounded review claim for a changed system state; no model score is produced.
        """,
        required_evidence_kinds=("run", "state", "evidence", "provenance", "integrity"),
        required_verification_conditions=(
            "chain_verified",
            "decision_rationale_present",
        ),
        allowed_decisions=("review",),
        required_reliability_states=("degraded",),
    ),
    ReliabilityClaimProfile(
        profile_id="compliance-handoff-ready",
        version="1",
        title="Compliance handoff ready",
        description="Evidence conditions for a portable compliance-oriented handoff.",
        required_evidence_kinds=(
            "run",
            "state",
            "evidence",
            "provenance",
            "integrity",
            "attestation",
        ),
        required_verification_conditions=(
            "chain_verified",
            "reconciliation_verified",
            "attestation_present",
            "decision_rationale_present",
        ),
        allowed_decisions=("accept", "review"),
        required_reconciliation_states=("verified", "recovered"),
        required_reliability_states=("reliable", "recovered"),
    ),
)


def get_builtin_claim_profile(
    profile_id: str, version: str = "1"
) -> ReliabilityClaimProfile:
    """Return a built-in reliability claim profile by identifier."""
    for profile in BUILTIN_CLAIM_PROFILES:
        if profile.profile_id == profile_id and profile.version == version:
            return profile
    raise KeyError(f"unknown claim profile: {profile_id}@{version}")
