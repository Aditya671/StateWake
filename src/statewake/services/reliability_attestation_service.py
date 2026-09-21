"""V1 reliability-outcome attestation service."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from ..adapters.reliability_attestation import JsonlReliabilityOutcomeAttestationStore
from ..domain.attestation_trust import SignedAttestationTrustState
from ..domain.reliability_attestation import (
    ReliabilityOutcomeAttestation,
    SignedReliabilityOutcomeEnvelope,
)
from ..domain.reliability_evidence import ReliabilityEvidenceChain
from ..domain.reliability_state import ReliabilityStateTransition
from ..services.persistence import atomic_write_text
from ..utils.signatures import verify_ed25519_signature


def _stable_id(
    subject_id: str,
    chain: ReliabilityEvidenceChain,
    transition: ReliabilityStateTransition,
    occurred_at: str,
) -> str:
    """Return the deterministic identifier for the reliability attestation."""
    payload = {
        "subject_id": subject_id,
        "evidence_chain_digest": chain.digest(),
        "transition_digest": transition.computed_digest,
        "decision": chain.decision,
        "reliability_state": transition.to_state,
        "occurred_at": occurred_at,
    }
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def attest_reliability_outcome(
    chain: ReliabilityEvidenceChain,
    transition: ReliabilityStateTransition,
    *,
    actor: str,
    store: JsonlReliabilityOutcomeAttestationStore,
    occurred_at: datetime | None = None,
    signing_key_id: str | None = None,
) -> ReliabilityOutcomeAttestation:
    """Create and persist a reliability outcome attestation."""
    if transition.evidence_chain_id != chain.chain_id:
        raise ValueError(
            "reliability state transition is not bound to the supplied evidence chain."
        )
    if transition.evidence_chain_digest != chain.digest():
        raise ValueError(
            "reliability state transition evidence-chain digest does not match the supplied chain."
        )
    if transition.subject_id.strip() == "":
        raise ValueError("transition subject_id must not be empty.")
    when = (occurred_at or datetime.now(UTC)).astimezone(UTC).isoformat()
    records = store.read()
    previous = records[-1].digest if records else ""
    attestation = ReliabilityOutcomeAttestation(
        attestation_id=_stable_id(transition.subject_id, chain, transition, when),
        subject_id=transition.subject_id,
        occurred_at=when,
        actor=actor,
        evidence_chain_id=chain.chain_id,
        evidence_chain_digest=chain.digest(),
        transition_id=transition.transition_id,
        transition_digest=transition.computed_digest,
        reliability_state=transition.to_state,
        decision=transition.decision,
        verification_status=chain.verification_status,
        reconciliation_state=chain.reconciliation_state,
        decision_rationale=transition.rationale or chain.decision_rationale,
        signing_key_id=signing_key_id,
        previous_digest=previous,
    )
    return store.append(attestation)


def verify_reliability_outcome_binding(
    attestation: ReliabilityOutcomeAttestation,
    chain: ReliabilityEvidenceChain,
    transition: ReliabilityStateTransition,
) -> None:
    """Verify the binding between an outcome and its evidence/state context."""
    if (
        attestation.evidence_chain_id != chain.chain_id
        or attestation.evidence_chain_digest != chain.digest()
    ):
        raise ValueError("attestation evidence-chain binding verification failed.")
    if (
        attestation.transition_id != transition.transition_id
        or attestation.transition_digest != transition.computed_digest
    ):
        raise ValueError(
            "attestation reliability-state transition binding verification failed."
        )
    if (
        attestation.subject_id != transition.subject_id
        or attestation.reliability_state != transition.to_state
        or attestation.decision != transition.decision
    ):
        raise ValueError("attestation outcome binding verification failed.")
    if (
        attestation.verification_status != chain.verification_status
        or attestation.reconciliation_state != chain.reconciliation_state
    ):
        raise ValueError(
            "attestation verification/reconciliation binding verification failed."
        )
    if attestation.digest != attestation.computed_digest():
        raise ValueError("reliability outcome attestation digest verification failed.")


def write_reliability_outcome_attestation(
    attestation: ReliabilityOutcomeAttestation, path: Path
) -> None:
    """Persist a reliability outcome attestation."""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        path, json.dumps(attestation.to_dict(), indent=2, sort_keys=True) + "\n"
    )


def load_reliability_outcome_attestation(path: Path) -> ReliabilityOutcomeAttestation:
    """Load and validate a persisted reliability outcome attestation."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("reliability outcome attestation root must be an object.")
    return ReliabilityOutcomeAttestation.from_dict(payload)


def create_signed_reliability_outcome_envelope(
    attestation: ReliabilityOutcomeAttestation, *, key_id: str, signature: bytes
) -> SignedReliabilityOutcomeEnvelope:
    """Create a signed reliability outcome envelope with its trust bindings."""
    from base64 import urlsafe_b64encode

    payload = attestation.to_dict()
    return SignedReliabilityOutcomeEnvelope(
        algorithm="Ed25519",
        key_id=key_id,
        attestation=payload,
        payload_digest=sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        ).hexdigest(),
        signature=urlsafe_b64encode(signature).rstrip(b"=").decode("ascii"),
    )


def verify_signed_reliability_outcome_envelope(
    envelope: SignedReliabilityOutcomeEnvelope,
    *,
    trusted_public_keys: dict[str, bytes],
    trust_state: SignedAttestationTrustState | None = None,
) -> ReliabilityOutcomeAttestation:
    """Verify the signature and bindings of a signed reliability outcome envelope."""
    from base64 import urlsafe_b64decode

    from ..domain.attestation_trust import attestation_signing_key_status

    keys = dict(trusted_public_keys)
    if trust_state is not None:
        anchor = attestation_signing_key_status(trust_state, envelope.key_id)
        if keys.get(anchor.key_id) != anchor.public_key:
            raise ValueError(f"attestation trust key mismatch for {anchor.key_id}.")
        public_key = anchor.public_key
    else:
        try:
            public_key = keys[envelope.key_id]
        except KeyError as exc:
            raise ValueError(
                f"unknown reliability attestation signing key: {envelope.key_id}"
            ) from exc
    signature = urlsafe_b64decode(
        envelope.signature + "=" * (-len(envelope.signature) % 4)
    )
    try:
        verify_ed25519_signature(public_key, envelope.payload_bytes(), signature)
    except ValueError as exc:
        raise ValueError(
            "reliability outcome attestation signature verification failed."
        ) from exc
    return ReliabilityOutcomeAttestation.from_dict(envelope.attestation)
