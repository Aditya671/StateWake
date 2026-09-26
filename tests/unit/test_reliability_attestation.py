"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from nacl.signing import SigningKey

from statewake.adapters.reliability_attestation import (
    JsonlReliabilityOutcomeAttestationStore,
)
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.domain.reliability_state import ReliabilityStateTransition
from statewake.services.reliability_attestation_service import (
    attest_reliability_outcome,
    verify_reliability_outcome_binding,
)

NOW = datetime(2026, 9, 10, 12, tzinfo=UTC)
DIGESTS = ["a" * 64, "b" * 64, "c" * 64, "d" * 64, "e" * 64, "f" * 64]


def chain(decision="accept", state="reliable", recon="verified"):
    """Verify the `chain` behavior and its expected invariants."""
    return ReliabilityEvidenceChain(
        chain_id="chain-1",
        run=EvidenceReference("run", "run-1", DIGESTS[0]),
        state=EvidenceReference("state", "state-1", DIGESTS[1]),
        evidence=(EvidenceReference("evidence", "ev-1", DIGESTS[2]),),
        provenance=EvidenceReference("provenance", "prov-1", DIGESTS[3]),
        integrity=EvidenceReference("integrity", "int-1", DIGESTS[4]),
        verification_status="verified",
        reliability_state=state,
        reconciliation_state=recon,
        decision=decision,
        decision_rationale=("verified inputs",),
    )


def transition(c):
    """Verify the `transition` behavior and its expected invariants."""
    return ReliabilityStateTransition(
        transition_id="t-1",
        subject_id="agent-1",
        from_state="unknown",
        to_state=c.reliability_state,
        occurred_at=NOW,
        actor="operator",
        evidence_chain_id=c.chain_id,
        evidence_chain_digest=c.digest(),
        decision=c.decision,
        rationale=c.decision_rationale,
    )


class TestReliabilityOutcomeAttestation(unittest.TestCase):
    """
    Provide regression coverage for the TestReliabilityOutcomeAttestation behavior.
    """

    def test_binds_chain_and_transition(self):
        """Verify the `test_binds_chain_and_transition` behavior
        and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            store = JsonlReliabilityOutcomeAttestationStore(Path(d) / "att.jsonl")
            c = chain()
            t = transition(c)
            att = attest_reliability_outcome(
                c, t, actor="operator", store=store, occurred_at=NOW
            )
            verify_reliability_outcome_binding(att, c, t)
            self.assertEqual(att.evidence_chain_digest, c.digest())
            self.assertEqual(att.transition_digest, t.computed_digest)
            self.assertEqual(store.read()[0].digest, att.digest)

    def test_rejects_mismatched_chain_digest(self):
        """Verify the `test_rejects_mismatched_chain_digest` behavior
        and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            c = chain()
            t = transition(c)
            bad = ReliabilityStateTransition.from_dict(
                {**t.to_dict(include_digest=False), "evidence_chain_digest": "9" * 64}
            )
            with self.assertRaises(ValueError):
                attest_reliability_outcome(
                    c,
                    bad,
                    actor="operator",
                    store=JsonlReliabilityOutcomeAttestationStore(Path(d) / "a.jsonl"),
                    occurred_at=NOW,
                )

    def test_exact_retry_is_idempotent(self):
        """Verify the `test_exact_retry_is_idempotent` behavior
        and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            store = JsonlReliabilityOutcomeAttestationStore(Path(d) / "a.jsonl")
            c = chain()
            t = transition(c)
            a1 = attest_reliability_outcome(
                c, t, actor="operator", store=store, occurred_at=NOW
            )
            a2 = attest_reliability_outcome(
                c, t, actor="operator", store=store, occurred_at=NOW
            )
            self.assertEqual(a1, a2)
            self.assertEqual(len(store.read()), 1)

    def test_chain_tamper_is_rejected(self):
        """Verify the `test_chain_tamper_is_rejected` behavior
        and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "a.jsonl"
            store = JsonlReliabilityOutcomeAttestationStore(path)
            c = chain()
            t = transition(c)
            attest_reliability_outcome(
                c, t, actor="operator", store=store, occurred_at=NOW
            )
            payload = json.loads(path.read_text().splitlines()[0])
            payload["decision_rationale"] = ["tampered"]
            path.write_text(json.dumps(payload) + "\n")
            with self.assertRaises(ValueError):
                store.read()

    def test_recovered_requires_recovered_reconciliation(self):
        """Verify the `test_recovered_requires_recovered_reconciliation` behavior
        and its expected invariants."""
        with tempfile.TemporaryDirectory():
            bad = chain(state="recovered", recon="verified")
            with self.assertRaises(ValueError):
                transition(bad)

    def test_requires_verified_reconciliation(self):
        """Verify the `test_requires_verified_reconciliation` behavior
        and its expected invariants."""
        with self.assertRaises(ValueError):
            chain(decision="accept", state="reliable", recon="pending")

    def test_from_dict_rejects_digest_tamper(self):
        """Verify the `test_from_dict_rejects_digest_tamper` behavior
        and its expected invariants."""
        c = chain()
        t = transition(c)
        with tempfile.TemporaryDirectory() as d:
            a = attest_reliability_outcome(
                c,
                t,
                actor="operator",
                store=JsonlReliabilityOutcomeAttestationStore(Path(d) / "a.jsonl"),
                occurred_at=NOW,
            )
        payload = a.to_dict()
        payload["decision"] = "reject"
        with self.assertRaises(ValueError):
            type(a).from_dict(payload)


class TestSignedReliabilityOutcome(unittest.TestCase):
    """Provide regression coverage for the TestSignedReliabilityOutcome behavior."""

    def test_signed_envelope_round_trip(self):
        """Verify the `test_signed_envelope_round_trip` behavior
        and its expected invariants."""
        from statewake.domain.reliability_attestation import (
            SignedReliabilityOutcomeEnvelope,
        )
        from statewake.services.reliability_attestation_service import (
            create_signed_reliability_outcome_envelope,
            verify_signed_reliability_outcome_envelope,
        )

        with tempfile.TemporaryDirectory() as d:
            c = chain()
            t = transition(c)
            store = JsonlReliabilityOutcomeAttestationStore(Path(d) / "a.jsonl")
            att = attest_reliability_outcome(
                c, t, actor="operator", store=store, occurred_at=NOW
            )
            private = SigningKey.generate()
            public = private.verify_key.encode()
            unsigned_payload = att.to_dict()
            import json
            from hashlib import sha256

            pd = sha256(
                json.dumps(
                    unsigned_payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode()
            ).hexdigest()
            envelope_payload = {"attestation": unsigned_payload, "payload_digest": pd}
            sig = private.sign(
                json.dumps(
                    envelope_payload,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode()
            ).signature
            envelope = create_signed_reliability_outcome_envelope(
                att, key_id="k1", signature=sig
            )
            verified = verify_signed_reliability_outcome_envelope(
                envelope, trusted_public_keys={"k1": public}
            )
            self.assertEqual(verified, att)
            self.assertEqual(
                SignedReliabilityOutcomeEnvelope.from_dict(envelope.to_dict()), envelope
            )

    def test_signed_payload_tamper_is_rejected(self):
        """Verify the `test_signed_payload_tamper_is_rejected` behavior
        and its expected invariants."""
        from statewake.services.reliability_attestation_service import (
            create_signed_reliability_outcome_envelope,
            verify_signed_reliability_outcome_envelope,
        )

        with tempfile.TemporaryDirectory() as d:
            c = chain()
            t = transition(c)
            att = attest_reliability_outcome(
                c,
                t,
                actor="operator",
                store=JsonlReliabilityOutcomeAttestationStore(Path(d) / "a.jsonl"),
                occurred_at=NOW,
            )
            private = SigningKey.generate()
            public = private.verify_key.encode()
            envelope = create_signed_reliability_outcome_envelope(
                att,
                key_id="k1",
                signature=private.sign(
                    create_signed_reliability_outcome_envelope(
                        att, key_id="k1", signature=b"0"
                    ).payload_bytes()
                ).signature,
            )
            tampered = envelope.to_dict()
            tampered["attestation"]["reliability_state"] = "unreliable"
            from statewake.domain.reliability_attestation import (
                SignedReliabilityOutcomeEnvelope,
            )

            with self.assertRaises(ValueError):
                verify_signed_reliability_outcome_envelope(
                    SignedReliabilityOutcomeEnvelope.from_dict(tampered),
                    trusted_public_keys={"k1": public},
                )


if __name__ == "__main__":
    unittest.main()
