"""Verification and persistence helpers for V1 reliability decision-basis artifacts."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

from statewake.utils.json_support import load_object

from ..domain.reliability_claim_profile import ReliabilityClaimProfile
from ..domain.reliability_decision_basis import ReliabilityDecisionBasis
from ..domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from ..services.persistence import atomic_write_text


def load_reliability_decision_basis(path: Path) -> ReliabilityDecisionBasis:
    """Load and validate a persisted reliability decision basis."""
    payload = load_object(path)
    if not isinstance(payload, dict):
        raise ValueError("reliability decision basis root must be an object.")
    return ReliabilityDecisionBasis.from_dict(payload)


def write_reliability_decision_basis(
    basis: ReliabilityDecisionBasis, path: Path
) -> None:
    """Persist a reliability decision basis."""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        path, json.dumps(basis.to_dict(), indent=2, sort_keys=True) + "\n"
    )


def build_reliability_decision_basis(
    chain: ReliabilityEvidenceChain,
    profile: ReliabilityClaimProfile,
    *,
    basis_id: str | None = None,
    version: str | None = None,
) -> ReliabilityDecisionBasis:
    """Build a deterministic decision basis from a satisfied claim profile and chain.

    This preparation step intentionally occurs before state-transition/attestation binding,
    because those downstream artifacts bind the final evidence-chain digest.
    """
    from ..services.reliability_claim_profile_service import evaluate_claim_profile

    evaluation = evaluate_claim_profile(chain, profile)
    if not evaluation.satisfied:
        raise ValueError(
            "claim profile was not satisfied: "
            + "; ".join(evaluation.failed_conditions)
        )
    inputs = (
        chain.run.digest,
        chain.state.digest,
        *(item.digest for item in chain.evidence),
        chain.provenance.digest,
        chain.integrity.digest,
    )
    if chain.reconciliation_ref is not None:
        inputs += (chain.reconciliation_ref.digest,)
    if chain.recovery_ref is not None:
        inputs += (chain.recovery_ref.digest,)
    if chain.attestation_ref is not None:
        inputs += (chain.attestation_ref.digest,)
    return ReliabilityDecisionBasis(
        format_version="1",
        basis_type="rule",
        basis_id=basis_id or f"claim-profile:{profile.profile_id}",
        version=version or profile.version,
        decision=chain.decision,
        reliability_state=chain.reliability_state,
        rationale=chain.decision_rationale,
        input_digests=tuple(dict.fromkeys(inputs)),
    )


def prepare_reliability_decision_basis(
    chain: ReliabilityEvidenceChain,
    profile: ReliabilityClaimProfile,
    *,
    basis_path: Path,
    output_chain_path: Path,
    basis_id: str | None = None,
    version: str | None = None,
) -> ReliabilityEvidenceChain:
    """Create and bind the claim-derived decision basis before downstream state/attestation binding."""
    if basis_path.parent.resolve() != output_chain_path.parent.resolve():
        raise ValueError(
            "basis_path and output_chain_path must share the same parent so the chain stores a portable source name"
        )
    basis = build_reliability_decision_basis(
        chain, profile, basis_id=basis_id, version=version
    )
    write_reliability_decision_basis(basis, basis_path)
    from dataclasses import replace

    reference = EvidenceReference(
        kind="decision-basis",
        identity=basis.basis_id,
        digest=_file_digest(basis_path),
        source=basis_path.name,
    )
    bound = replace(chain, decision_basis_ref=reference)
    atomic_write_text(
        output_chain_path, json.dumps(bound.to_dict(), indent=2, sort_keys=True) + "\n"
    )
    verify_reliability_decision_basis(bound, root=output_chain_path.parent)
    return bound


def _file_digest(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    return sha256(path.read_bytes()).hexdigest()


def verify_reliability_decision_basis(
    chain: ReliabilityEvidenceChain, *, root: Path
) -> None:
    """Verify a decision-basis artifact and its semantic binding to the reliability chain."""
    reference = chain.decision_basis_ref
    if reference is None:
        return
    if reference.source is None:
        raise ValueError(
            "decision_basis_ref must retain a verifiable local artifact source"
        )
    candidate = (root.resolve() / reference.source.replace("\\", "/")).resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError(
            f"reliability decision basis source escapes root: {reference.source}"
        )
    if not candidate.is_file():
        raise FileNotFoundError(
            f"reliability decision basis source not found: {candidate}"
        )
    actual = _file_digest(candidate)
    if actual != reference.digest:
        raise ValueError(
            f"reliability decision basis source digest mismatch for {reference.identity}: expected {reference.digest}, got {actual}"
        )
    basis = load_reliability_decision_basis(candidate)
    expected_kind = "policy" if basis.basis_type == "policy" else "decision-basis"
    if reference.kind != expected_kind:
        raise ValueError("decision-basis reference kind does not match basis_type")
    if basis.basis_id != reference.identity:
        raise ValueError(
            "decision-basis identity does not match its evidence reference"
        )
    if basis.decision != chain.decision:
        raise ValueError(
            "decision-basis decision does not match reliability chain decision"
        )
    if basis.reliability_state != chain.reliability_state:
        raise ValueError(
            "decision-basis reliability state does not match reliability chain state"
        )
    if tuple(basis.rationale) != tuple(chain.decision_rationale):
        raise ValueError(
            "decision-basis rationale does not match reliability chain rationale"
        )
    allowed_inputs = {
        chain.run.digest,
        chain.state.digest,
        *(item.digest for item in chain.evidence),
        chain.provenance.digest,
        chain.integrity.digest,
    }
    if chain.reconciliation_ref is not None:
        allowed_inputs.add(chain.reconciliation_ref.digest)
    if chain.recovery_ref is not None:
        allowed_inputs.add(chain.recovery_ref.digest)
    if chain.attestation_ref is not None:
        allowed_inputs.add(chain.attestation_ref.digest)
    missing = [item for item in basis.input_digests if item not in allowed_inputs]
    if missing:
        raise ValueError(
            f"decision-basis references inputs outside the reliability evidence chain: {missing}"
        )
