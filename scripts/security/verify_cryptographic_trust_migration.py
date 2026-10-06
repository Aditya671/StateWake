"""Portable verifier for Tier 15 cryptographic/trust-migration semantics."""

from __future__ import annotations

import json
import sys
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from statewake.adapters.attestation_trust_history import (  # noqa: E402
    JsonlAttestationTrustHistoryStore,
)
from statewake.adapters.reliability_attestation import (  # noqa: E402
    JsonlReliabilityOutcomeAttestationStore,
    SignedReliabilityOutcomeBinding,
)
from statewake.domain.attestation_trust import (  # noqa: E402
    AttestationTrustAnchor,
    SignedAttestationTrustState,
)
from statewake.domain.cryptographic_trust import (  # noqa: E402
    CryptographicAlgorithm,
    CryptographicKeyIdentity,
    CryptographicProfile,
    KeyStatus,
    ProofFormatMigration,
    TrustMigration,
    rotate_key,
    validate_algorithm_transition,
    validate_historical_verification,
)
from statewake.domain.reliability_attestation import (  # noqa: E402
    ReliabilityOutcomeAttestation,
    SignedReliabilityOutcomeEnvelope,
)
from statewake.domain.reliability_attestation_trust_context import (  # noqa: E402
    ReliabilityAttestationTrustContext,
)


class _TrustStateVerifier:
    """Deterministic verifier used only by this portable semantic check."""

    def verify(self, state: SignedAttestationTrustState) -> SignedAttestationTrustState:
        return state


def _verify_durable_attestation_trust_history() -> None:
    """Verify append-only signed-state history and non-reactivation semantics."""
    first = SignedAttestationTrustState(
        authority_key_id="authority-1",
        version=1,
        issued_at="2026-10-01T00:00:01+00:00",
        anchors=(AttestationTrustAnchor("key-v1", b"A" * 32),),
        signature="sig-1",
        previous_digest=None,
    )
    second = SignedAttestationTrustState(
        authority_key_id="authority-1",
        version=2,
        issued_at="2026-10-01T00:00:02+00:00",
        anchors=(
            AttestationTrustAnchor("key-v1", b"A" * 32, "superseded", "key-v2"),
            AttestationTrustAnchor("key-v2", b"B" * 32),
        ),
        signature="sig-2",
        previous_digest=first.digest(),
    )
    with TemporaryDirectory() as temporary:
        store = JsonlAttestationTrustHistoryStore(
            Path(temporary) / "attestation-trust-history.jsonl",
            _TrustStateVerifier(),
        )
        store.append(first)
        store.append(second)
        if store.read() != (first, second):
            raise AssertionError("attestation trust history did not round-trip")


def _verify_canonical_signed_attestation_binding() -> None:
    """Verify durable signed-envelope/trust-context persistence without private keys."""
    attestation = ReliabilityOutcomeAttestation(
        attestation_id="attestation-1",
        subject_id="subject-1",
        occurred_at="2026-10-01T00:00:00+00:00",
        actor="tier15",
        evidence_chain_id="chain-1",
        evidence_chain_digest="a" * 64,
        transition_id="transition-1",
        transition_digest="b" * 64,
        reliability_state="reliable",
        decision="accept",
        verification_status="verified",
        reconciliation_state="verified",
        signing_key_id="key-v1",
    )
    envelope = SignedReliabilityOutcomeEnvelope(
        algorithm="Ed25519",
        key_id="key-v1",
        attestation=attestation.to_dict(),
        payload_digest=sha256(
            json.dumps(
                attestation.to_dict(),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest(),
        signature="c2lnbmF0dXJl",
    )
    envelope_digest = sha256(
        json.dumps(
            envelope.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    context = ReliabilityAttestationTrustContext(
        format_version="1",
        envelope_artifact_id="attestation-envelope:attestation-1",
        envelope_digest=envelope_digest,
        attestation_id=attestation.attestation_id,
        attestation_digest=attestation.digest,
        signing_key_id="key-v1",
        signing_key_digest="c" * 64,
        trust_state_artifact_id="trust-state:1",
        trust_state_digest="d" * 64,
        trust_state_version=1,
        authority_store_artifact_id="authority-store:1",
        authority_key_id="authority-1",
        authority_key_digest="e" * 64,
    )
    binding = SignedReliabilityOutcomeBinding(envelope, context)
    with TemporaryDirectory() as temporary:
        store = JsonlReliabilityOutcomeAttestationStore(
            Path(temporary) / "reliability-attestations.jsonl"
        )
        if store.append_signed(binding) != binding:
            raise AssertionError("signed attestation binding did not append")
        if store.append_signed(binding) != binding:
            raise AssertionError("signed attestation exact retry was not idempotent")
        if store.read() != [attestation]:
            raise AssertionError("legacy attestation read changed after signed binding")
        if store.read_signed_bindings() != (binding,):
            raise AssertionError("signed attestation binding did not round-trip")


def main() -> int:
    """Run the deterministic Tier 15 contract checks."""
    ed25519 = CryptographicAlgorithm("Ed25519", "")
    sha256 = CryptographicAlgorithm("SHA-256", "")
    old = CryptographicProfile("1", "1", sha256, ed25519, "1", ("1",))
    new = CryptographicProfile("2", "2", sha256, ed25519, "2", ("1", "2"))
    current = CryptographicKeyIdentity("key-v1", 1, ed25519, "a" * 64)
    replacement = CryptographicKeyIdentity("key-v2", 2, ed25519, "b" * 64)
    historical, _, _ = rotate_key(
        current,
        replacement,
        authority="tier15-authority",
        rationale="planned key rotation",
    )
    migration = TrustMigration(
        migration_id="migration-1",
        from_root_id="root-v1",
        from_root_version=1,
        to_root_id="root-v2",
        to_root_version=2,
        transition_authority="root-transition-authority",
        activation_boundary="proof-schema-v2",
        verification_policy_version="2",
    )
    validate_algorithm_transition(old, new, migration=migration)
    validate_historical_verification(historical, old)
    ProofFormatMigration("1", "2", "2", "read-both", "proof-authority")
    if historical.status is not KeyStatus.SUPERSEDED:
        raise AssertionError("rotated key did not become historical")
    _verify_durable_attestation_trust_history()
    _verify_canonical_signed_attestation_binding()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
