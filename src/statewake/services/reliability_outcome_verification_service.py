"""End-to-end verification for the V1 reliability outcome chain."""

from __future__ import annotations

from pathlib import Path

from ..adapters.reliability_state import JsonlReliabilityStateStore
from ..domain.reliability_attestation import ReliabilityOutcomeAttestation
from ..domain.reliability_evidence import ReliabilityEvidenceChain
from ..domain.reliability_outcome_verification import (
    ReliabilityOutcomeVerificationReport,
)
from ..domain.reliability_state import ReliabilityStateTransition
from ..services.reliability_evidence_service import verify_reliability_evidence_chain
from ..services.reliability_recovery_service import verify_reliability_recovery_outcome
from .reliability_attestation_service import verify_reliability_outcome_binding


def _transition_for_attestation(
    subject_id: str, attestation: ReliabilityOutcomeAttestation, history_path: Path
) -> ReliabilityStateTransition:
    """Return the state transition bound to a reliability attestation."""
    history = JsonlReliabilityStateStore(history_path).read(subject_id)
    matches = [
        item for item in history if item.transition_id == attestation.transition_id
    ]
    if not matches:
        raise ValueError(
            f"reliability-state transition not found: {attestation.transition_id}"
        )
    if len(matches) != 1:
        raise ValueError(
            f"reliability-state transition is not unique: {attestation.transition_id}"
        )
    return matches[0]


def verify_reliability_outcome(
    attestation: ReliabilityOutcomeAttestation,
    chain: ReliabilityEvidenceChain,
    *,
    subject_id: str,
    history_path: Path,
    evidence_root: Path,
) -> ReliabilityOutcomeVerificationReport:
    """Verify the reliability outcome and its required evidence bindings."""
    failures: list[str] = []
    checks: list[str] = []

    if attestation.subject_id != subject_id:
        failures.append("subject binding mismatch")

    try:
        if attestation.computed_digest() != attestation.digest:
            raise ValueError("attestation digest mismatch")
        checks.append("attestation_integrity")
    except ValueError as exc:
        failures.append(str(exc))

    try:
        chain_digest = chain.digest()
        if (
            attestation.evidence_chain_id != chain.chain_id
            or attestation.evidence_chain_digest != chain_digest
        ):
            raise ValueError("attestation is not bound to the supplied evidence chain")
        verify_reliability_evidence_chain(chain, root=evidence_root)
        checks.extend(("evidence_chain_integrity", "evidence_sources"))
    except (FileNotFoundError, ValueError) as exc:
        failures.append(str(exc))

    transition: ReliabilityStateTransition | None = None
    try:
        transition = _transition_for_attestation(subject_id, attestation, history_path)
        if transition.computed_digest != attestation.transition_digest:
            raise ValueError(
                "attestation transition digest does not match authoritative history"
            )
        if (
            transition.evidence_chain_id != chain.chain_id
            or transition.evidence_chain_digest != chain.digest()
        ):
            raise ValueError(
                "authoritative transition is not bound to the supplied evidence chain"
            )
        checks.extend(("state_transition_integrity", "state_transition_binding"))
    except (ValueError, OSError) as exc:
        failures.append(str(exc))

    if transition is not None:
        try:
            if (
                transition.subject_id != attestation.subject_id
                or transition.subject_id != subject_id
            ):
                raise ValueError("subject binding mismatch")
            if (
                transition.to_state != attestation.reliability_state
                or transition.decision != attestation.decision
            ):
                raise ValueError(
                    "attested outcome does not match authoritative transition"
                )
            expected = {
                "reliable": "accept",
                "recovered": "accept",
                "degraded": "review",
                "unreliable": "reject",
            }[transition.to_state]
            if transition.decision != expected:
                raise ValueError(
                    "authoritative transition decision/state semantics are invalid"
                )
            if (
                transition.to_state == "recovered"
                and chain.reconciliation_state != "recovered"
            ):
                raise ValueError(
                    "recovered outcome lacks recovered reconciliation state"
                )
            checks.append("outcome_semantics")
            if chain.comparison_ref is not None:
                checks.append("comparison_binding")
            if chain.reconciliation_binding_ref is not None:
                checks.append("reconciliation_binding")
            if transition.to_state == "recovered":
                verify_reliability_recovery_outcome(chain, root=evidence_root)
                checks.append("recovery_outcome_binding")
        except ValueError as exc:
            failures.append(str(exc))

        try:
            verify_reliability_outcome_binding(attestation, chain, transition)
            checks.append("attestation_binding")
        except ValueError as exc:
            failures.append(str(exc))

    expected_checks = {
        "attestation_integrity",
        "evidence_chain_integrity",
        "evidence_sources",
        "state_transition_integrity",
        "state_transition_binding",
        "outcome_semantics",
        "attestation_binding",
    }
    if chain.reliability_state == "recovered":
        expected_checks.add("recovery_outcome_binding")
    if chain.comparison_ref is not None:
        expected_checks.add("comparison_binding")
    if chain.reconciliation_binding_ref is not None:
        expected_checks.add("reconciliation_binding")
    verified = not failures and set(checks) == expected_checks
    return ReliabilityOutcomeVerificationReport(
        attestation_id=attestation.attestation_id,
        subject_id=subject_id,
        verified=verified,
        checks=tuple(checks),
        failures=tuple(failures),
    )
