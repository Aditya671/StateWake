"""V1 reliability-outcome attestation service."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from ..adapters.key_management import ExternalSigningAdapter
from ..adapters.reliability_attestation import (
    JsonlReliabilityOutcomeAttestationStore,
    SignedReliabilityOutcomeBinding,
)
from ..domain.attestation_trust import (
    Ed25519AttestationTrustStateVerifier,
    SignedAttestationTrustState,
    attestation_signing_key_status,
)
from ..domain.key_management import SigningKeyReference
from ..domain.reliability_attestation import (
    ReliabilityOutcomeAttestation,
    SignedReliabilityOutcomeEnvelope,
)
from ..domain.reliability_attestation_trust_context import (
    ReliabilityAttestationTrustContext,
)
from ..domain.reliability_evidence import ReliabilityEvidenceChain
from ..domain.reliability_state import ReliabilityStateTransition
from ..services.persistence import atomic_write_text
from ..utils.signatures import verify_ed25519_signature


def _canonical(payload: dict[str, object]) -> bytes:
    """Return canonical JSON bytes used by signed-attestation bindings."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


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


def _build_reliability_outcome_attestation(
    chain: ReliabilityEvidenceChain,
    transition: ReliabilityStateTransition,
    *,
    actor: str,
    store: JsonlReliabilityOutcomeAttestationStore,
    occurred_at: datetime | None,
    signing_key_id: str | None,
) -> ReliabilityOutcomeAttestation:
    """Build an attestation against the current canonical chain tip without writing it."""
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
    return ReliabilityOutcomeAttestation(
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
    attestation = _build_reliability_outcome_attestation(
        chain,
        transition,
        actor=actor,
        store=store,
        occurred_at=occurred_at,
        signing_key_id=signing_key_id,
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
        payload_digest=sha256(_canonical(payload)).hexdigest(),
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
    attestation = ReliabilityOutcomeAttestation.from_dict(envelope.attestation)
    if attestation.signing_key_id != envelope.key_id:
        raise ValueError(
            "signed reliability envelope key does not match attestation signing_key_id."
        )
    return attestation


def build_reliability_attestation_trust_context(
    envelope: SignedReliabilityOutcomeEnvelope,
    *,
    trust_state: SignedAttestationTrustState,
    authority_store: Mapping[str, bytes],
    envelope_artifact_id: str | None = None,
    trust_state_artifact_id: str | None = None,
    authority_store_artifact_id: str | None = None,
) -> ReliabilityAttestationTrustContext:
    """Authenticate and bind one signed attestation to the exact trust state used."""
    authorities = dict(authority_store)
    Ed25519AttestationTrustStateVerifier(authorities).verify(trust_state)
    attestation = verify_signed_reliability_outcome_envelope(
        envelope,
        trusted_public_keys={
            anchor.key_id: anchor.public_key for anchor in trust_state.anchors
        },
        trust_state=trust_state,
    )
    anchor = attestation_signing_key_status(trust_state, envelope.key_id)
    try:
        authority_key = authorities[trust_state.authority_key_id]
    except KeyError as exc:
        raise ValueError(
            "attestation trust-state authority key is absent from the authority store"
        ) from exc
    state_digest = trust_state.digest()
    return ReliabilityAttestationTrustContext(
        format_version="1",
        envelope_artifact_id=(
            envelope_artifact_id or f"attestation-envelope:{attestation.attestation_id}"
        ),
        envelope_digest=sha256(_canonical(envelope.to_dict())).hexdigest(),
        attestation_id=attestation.attestation_id,
        attestation_digest=attestation.digest,
        signing_key_id=envelope.key_id,
        signing_key_digest=sha256(anchor.public_key).hexdigest(),
        trust_state_artifact_id=(
            trust_state_artifact_id
            or f"attestation-trust-state:{trust_state.version}:{state_digest}"
        ),
        trust_state_digest=state_digest,
        trust_state_version=trust_state.version,
        authority_store_artifact_id=(
            authority_store_artifact_id
            or f"attestation-authority:{trust_state.authority_key_id}"
        ),
        authority_key_id=trust_state.authority_key_id,
        authority_key_digest=sha256(authority_key).hexdigest(),
    )


def verify_reliability_attestation_trust_context(
    binding: SignedReliabilityOutcomeBinding,
    *,
    trust_state: SignedAttestationTrustState,
    authority_store: Mapping[str, bytes],
) -> ReliabilityOutcomeAttestation:
    """Verify a persisted signed binding against its exact authenticated trust state."""
    context = binding.trust_context
    if trust_state.version != context.trust_state_version:
        raise ValueError("signed attestation trust-state version mismatch")
    if trust_state.digest() != context.trust_state_digest:
        raise ValueError("signed attestation trust-state digest mismatch")
    if trust_state.authority_key_id != context.authority_key_id:
        raise ValueError("signed attestation authority identity mismatch")
    authorities = dict(authority_store)
    try:
        authority_key = authorities[context.authority_key_id]
    except KeyError as exc:
        raise ValueError(
            "signed attestation authority key is absent from the authority store"
        ) from exc
    if sha256(authority_key).hexdigest() != context.authority_key_digest:
        raise ValueError("signed attestation authority key digest mismatch")
    Ed25519AttestationTrustStateVerifier(authorities).verify(trust_state)
    anchor = attestation_signing_key_status(trust_state, context.signing_key_id)
    if sha256(anchor.public_key).hexdigest() != context.signing_key_digest:
        raise ValueError("signed attestation signing key digest mismatch")
    return verify_signed_reliability_outcome_envelope(
        binding.envelope,
        trusted_public_keys={
            item.key_id: item.public_key for item in trust_state.anchors
        },
        trust_state=trust_state,
    )


def resolve_reliability_attestation_trust_state(
    binding: SignedReliabilityOutcomeBinding,
    *,
    trust_states: Iterable[SignedAttestationTrustState],
) -> SignedAttestationTrustState:
    """Resolve the exact version/digest trust state recorded by one signed binding."""
    context = binding.trust_context
    expected = (context.trust_state_version, context.trust_state_digest)
    resolved: SignedAttestationTrustState | None = None
    for state in trust_states:
        identity = (state.version, state.digest())
        if identity != expected:
            continue
        if resolved is not None and resolved.to_dict() != state.to_dict():
            raise ValueError(
                "conflicting attestation trust states share the signed binding identity"
            )
        resolved = state
    if resolved is None:
        raise ValueError(
            "signed attestation trust state is unavailable for recorded version/digest"
        )
    return resolved


def verify_persisted_signed_reliability_outcome(
    attestation: ReliabilityOutcomeAttestation,
    *,
    store: JsonlReliabilityOutcomeAttestationStore,
    trust_states: Iterable[SignedAttestationTrustState],
    authority_store: Mapping[str, bytes],
) -> SignedReliabilityOutcomeBinding:
    """Verify one canonical signed binding using its exact authenticated trust state."""
    matches = tuple(
        binding
        for binding in store.read_signed_bindings()
        if binding.attestation.attestation_id == attestation.attestation_id
    )
    if not matches:
        raise ValueError(
            f"canonical signed attestation binding not found: {attestation.attestation_id}"
        )
    if len(matches) != 1:
        raise ValueError(
            f"multiple signed attestation bindings found: {attestation.attestation_id}"
        )
    binding = matches[0]
    if binding.attestation != attestation:
        raise ValueError(
            "canonical signed attestation binding does not match the supplied attestation"
        )
    exact_state = resolve_reliability_attestation_trust_state(
        binding,
        trust_states=trust_states,
    )
    verified = verify_reliability_attestation_trust_context(
        binding,
        trust_state=exact_state,
        authority_store=authority_store,
    )
    if verified != attestation:
        raise ValueError("verified signed attestation identity/content mismatch")
    return binding


def record_signed_reliability_outcome(
    envelope: SignedReliabilityOutcomeEnvelope,
    *,
    trust_state: SignedAttestationTrustState,
    authority_store: Mapping[str, bytes],
    store: JsonlReliabilityOutcomeAttestationStore,
) -> SignedReliabilityOutcomeBinding:
    """Authenticate and persist a signed envelope plus its exact trust-state binding."""
    context = build_reliability_attestation_trust_context(
        envelope,
        trust_state=trust_state,
        authority_store=authority_store,
    )
    binding = SignedReliabilityOutcomeBinding(envelope, context)
    return store.append_signed(binding)


def sign_and_record_reliability_outcome(
    attestation: ReliabilityOutcomeAttestation,
    *,
    signing_adapter: ExternalSigningAdapter,
    signing_key: SigningKeyReference,
    trust_state: SignedAttestationTrustState,
    authority_store: Mapping[str, bytes],
    store: JsonlReliabilityOutcomeAttestationStore,
) -> SignedReliabilityOutcomeBinding:
    """Sign through an external key provider and persist the authenticated binding."""
    if attestation.signing_key_id != signing_key.key_id:
        raise ValueError(
            "attestation signing_key_id does not match the external signing key reference"
        )
    # Authenticate the exact trust-state snapshot before requesting any external
    # signature. This prevents a host signer from being invoked under an
    # unauthenticated or attacker-substituted signing policy.
    Ed25519AttestationTrustStateVerifier(dict(authority_store)).verify(trust_state)
    anchor = attestation_signing_key_status(trust_state, signing_key.key_id)
    anchor_digest = sha256(anchor.public_key).hexdigest()
    if (
        signing_key.public_key_digest is not None
        and signing_key.public_key_digest != anchor_digest
    ):
        raise ValueError(
            "external signing key digest does not match trust-state anchor"
        )
    placeholder = create_signed_reliability_outcome_envelope(
        attestation, key_id=signing_key.key_id, signature=b"placeholder"
    )
    signature = signing_adapter.sign(signing_key, placeholder.payload_bytes())
    envelope = create_signed_reliability_outcome_envelope(
        attestation, key_id=signing_key.key_id, signature=signature
    )
    return record_signed_reliability_outcome(
        envelope,
        trust_state=trust_state,
        authority_store=authority_store,
        store=store,
    )


def attest_signed_reliability_outcome(
    chain: ReliabilityEvidenceChain,
    transition: ReliabilityStateTransition,
    *,
    actor: str,
    store: JsonlReliabilityOutcomeAttestationStore,
    signing_adapter: ExternalSigningAdapter,
    signing_key: SigningKeyReference,
    trust_state: SignedAttestationTrustState,
    authority_store: Mapping[str, bytes],
    occurred_at: datetime | None = None,
) -> SignedReliabilityOutcomeBinding:
    """Create, externally sign, authenticate, and canonically persist one attestation."""
    attestation = _build_reliability_outcome_attestation(
        chain,
        transition,
        actor=actor,
        store=store,
        occurred_at=occurred_at,
        signing_key_id=signing_key.key_id,
    )
    return sign_and_record_reliability_outcome(
        attestation,
        signing_adapter=signing_adapter,
        signing_key=signing_key,
        trust_state=trust_state,
        authority_store=authority_store,
        store=store,
    )
