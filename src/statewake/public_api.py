"""Stable, framework-neutral public API for StateWake.

The functions in this module are the primary Python consumer contract.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .adapters.reliability_state import JsonlReliabilityStateStore
from .domain.evidence_admission import ExternalEvidenceAdmission
from .domain.evidence_receipt import ExternalEvidenceReceipt
from .domain.reliability_attestation import ReliabilityOutcomeAttestation
from .domain.reliability_evidence import ReliabilityEvidenceChain
from .domain.reliability_outcome_verification import (
    ReliabilityOutcomeVerificationReport,
)
from .domain.reliability_state import ReliabilityStateSnapshot
from .services.evidence_admission_service import admit_external_evidence
from .services.reliability_evidence_service import (
    build_reliability_evidence_chain,
    load_reliability_evidence_chain,
    verify_reliability_evidence_chain,
)
from .services.reliability_outcome_verification_service import (
    verify_reliability_outcome,
)
from .services.reliability_state_service import current_reliability_state


def admit_evidence(
    receipt: ExternalEvidenceReceipt,
    *,
    artifact_path: Path,
    receipt_path: Path | None = None,
    expected_run_id: str | None = None,
    expected_producer_type: str | None = None,
    expected_producer_id: str | None = None,
) -> ExternalEvidenceAdmission:
    """Admit one external evidence artifact through the canonical receipt boundary."""
    return admit_external_evidence(
        receipt,
        artifact_path=artifact_path,
        receipt_path=receipt_path,
        expected_run_id=expected_run_id,
        expected_producer_type=expected_producer_type,
        expected_producer_id=expected_producer_id,
    )


def write_evidence_chain(chain: ReliabilityEvidenceChain, path: Path) -> None:
    """Persist a reliability evidence chain through the supported API."""
    from .services.reliability_evidence_service import write_reliability_evidence_chain

    write_reliability_evidence_chain(chain, path)


def load_evidence_chain(path: Path) -> ReliabilityEvidenceChain:
    """Load a persisted reliability evidence chain through the stable API."""
    return load_reliability_evidence_chain(path)


def load_outcome_attestation(path: Path) -> ReliabilityOutcomeAttestation:
    """Load and validate a persisted reliability outcome attestation."""
    from .services.reliability_attestation_service import (
        load_reliability_outcome_attestation,
    )

    return load_reliability_outcome_attestation(path)


def write_outcome_attestation(
    attestation: ReliabilityOutcomeAttestation, path: Path
) -> None:
    """Persist a reliability outcome attestation through the stable API."""
    from .services.reliability_attestation_service import (
        write_reliability_outcome_attestation,
    )

    write_reliability_outcome_attestation(attestation, path)


def build_evidence_chain(
    *,
    run_id: str,
    run_path: Path,
    state_id: str,
    state_path: Path,
    evidence_paths: tuple[Path, ...],
    provenance_path: Path,
    integrity_proof_path: Path,
    verification_status: str = "verified",
    reliability_state: str = "reliable",
    reconciliation_state: str = "verified",
    reconciliation_path: Path | None = None,
    recovery_path: Path | None = None,
    attestation_path: Path | None = None,
    decision_basis_path: Path | None = None,
    decision_basis_kind: str = "decision-basis",
    decision: str = "accept",
    rationale: tuple[str, ...] = (),
    evidence_receipt_paths: Mapping[str, Path] | None = None,
    comparison_path: Path | None = None,
    reconciliation_binding_path: Path | None = None,
) -> ReliabilityEvidenceChain:
    """Build the canonical V1 evidence chain from typed artifact references."""
    return build_reliability_evidence_chain(
        run_id=run_id,
        run_path=run_path,
        state_id=state_id,
        state_path=state_path,
        evidence_paths=evidence_paths,
        provenance_path=provenance_path,
        integrity_proof_path=integrity_proof_path,
        verification_status=verification_status,
        reliability_state=reliability_state,
        reconciliation_state=reconciliation_state,
        reconciliation_path=reconciliation_path,
        recovery_path=recovery_path,
        attestation_path=attestation_path,
        decision_basis_path=decision_basis_path,
        decision_basis_kind=decision_basis_kind,
        decision=decision,
        rationale=rationale,
        evidence_receipt_paths=evidence_receipt_paths,
        comparison_path=comparison_path,
        reconciliation_binding_path=reconciliation_binding_path,
    )


def verify_evidence_chain(chain: ReliabilityEvidenceChain, *, root: Path) -> None:
    """Verify the canonical evidence chain and all bound sources."""
    verify_reliability_evidence_chain(chain, root=root)


def verify_outcome(
    attestation: ReliabilityOutcomeAttestation,
    chain: ReliabilityEvidenceChain,
    *,
    subject_id: str,
    history_path: Path,
    evidence_root: Path,
) -> ReliabilityOutcomeVerificationReport:
    """Independently verify a reliability outcome across evidence and state history."""
    return verify_reliability_outcome(
        attestation,
        chain,
        subject_id=subject_id,
        history_path=history_path,
        evidence_root=evidence_root,
    )


def read_reliability_state(
    subject_id: str, *, history_path: Path
) -> ReliabilityStateSnapshot:
    """Read the authoritative current reliability state for a subject."""
    return current_reliability_state(
        subject_id, store=JsonlReliabilityStateStore(history_path)
    )
