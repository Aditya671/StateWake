"""Tests for independent persistent trust anchors."""

from __future__ import annotations

import base64
import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from nacl.signing import SigningKey

from statewake.adapters.trust_anchor import JsonTrustAnchorStore
from statewake.domain.trust_anchor import (
    AnchorDiscrepancyError,
    TrustAnchorError,
    TrustCheckpoint,
    compare_local_tip,
    create_trust_checkpoint,
)


class _Verifier:
    def verify(self, checkpoint: TrustCheckpoint) -> TrustCheckpoint:
        expected = base64.urlsafe_b64encode(b"sig").rstrip(b"=").decode()
        if checkpoint.signature != expected:
            raise TrustAnchorError("bad signature")
        return checkpoint


def _checkpoint(
    checkpoint_id: str,
    tip: str,
    count: int,
    previous: str | None = None,
) -> TrustCheckpoint:
    return create_trust_checkpoint(
        checkpoint_id=checkpoint_id,
        subject_id="subject-1",
        issued_at=f"2026-09-13T00:00:{count:02d}Z",
        history_tip_digest=tip,
        history_record_count=count,
        signing_key_id="checkpoint-key-v1",
        signing_key_digest=hashlib.sha256(b"public-key").hexdigest(),
        signature=b"sig",
        previous_checkpoint_digest=previous,
    )


class TestTrustAnchor(unittest.TestCase):
    def test_checkpoint_round_trip_and_idempotent_publish(self) -> None:
        with TemporaryDirectory() as directory:
            store = JsonTrustAnchorStore(Path(directory), _Verifier())
            first = _checkpoint("cp-1", "a" * 64, 10)
            store.publish(first)
            store.publish(first)
            self.assertEqual(store.retrieve("cp-1"), first)
            self.assertEqual(store.latest(), first)

    def test_sequence_and_rollback_are_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            store = JsonTrustAnchorStore(Path(directory), _Verifier())
            first = _checkpoint("cp-1", "a" * 64, 10)
            store.publish(first)
            second = _checkpoint("cp-2", "b" * 64, 11, first.digest())
            store.publish(second)
            rollback = _checkpoint("cp-3", "c" * 64, 9, second.digest())
            with self.assertRaises(AnchorDiscrepancyError):
                store.publish(rollback)

    def test_anchor_disagreement_detects_deleted_trailing_history(self) -> None:
        checkpoint = _checkpoint("cp-1", "d" * 64, 20)
        with self.assertRaises(AnchorDiscrepancyError):
            compare_local_tip(
                checkpoint,
                history_tip_digest="c" * 64,
                history_record_count=19,
            )

    def test_multiple_subjects_have_independent_checkpoint_sequences(self) -> None:
        with TemporaryDirectory() as directory:
            store = JsonTrustAnchorStore(Path(directory), _Verifier())
            first = _checkpoint("cp-1", "a" * 64, 10)
            store.publish(first)
            second = create_trust_checkpoint(
                checkpoint_id="cp-2",
                subject_id="subject-2",
                issued_at="2026-09-13T00:00:01Z",
                history_tip_digest="b" * 64,
                history_record_count=1,
                signing_key_id="checkpoint-key-v1",
                signing_key_digest=hashlib.sha256(b"public-key").hexdigest(),
                signature=b"sig",
            )
            store.publish(second)
            self.assertEqual(store.latest(subject_id="subject-1"), first)
            self.assertEqual(store.latest(subject_id="subject-2"), second)
            with self.assertRaises(AnchorDiscrepancyError):
                store.latest()

    def test_checkpoint_id_conflict_is_not_silently_repaired(self) -> None:
        with TemporaryDirectory() as directory:
            store = JsonTrustAnchorStore(Path(directory), _Verifier())
            store.publish(_checkpoint("cp-1", "a" * 64, 10))
            with self.assertRaises(AnchorDiscrepancyError):
                store.publish(_checkpoint("cp-1", "b" * 64, 10))

    def test_tampered_persisted_checkpoint_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            signing_key = SigningKey(bytes(range(32)))
            public_key = signing_key.verify_key.encode()
            key_digest = hashlib.sha256(public_key).hexdigest()
            unsigned = create_trust_checkpoint(
                checkpoint_id="cp-1",
                subject_id="subject-1",
                issued_at="2026-09-13T00:00:10Z",
                history_tip_digest="a" * 64,
                history_record_count=10,
                signing_key_id="checkpoint-key-v1",
                signing_key_digest=key_digest,
                signature=b"placeholder",
            )
            checkpoint = create_trust_checkpoint(
                checkpoint_id="cp-1",
                subject_id="subject-1",
                issued_at="2026-09-13T00:00:10Z",
                history_tip_digest="a" * 64,
                history_record_count=10,
                signing_key_id="checkpoint-key-v1",
                signing_key_digest=key_digest,
                signature=signing_key.sign(unsigned.payload_bytes()).signature,
            )
            from statewake.domain.trust_anchor import Ed25519TrustCheckpointVerifier

            store = JsonTrustAnchorStore(
                root,
                Ed25519TrustCheckpointVerifier({"checkpoint-key-v1": public_key}),
            )
            store.publish(checkpoint)
            payload = json.loads((root / "cp-1.json").read_text(encoding="utf-8"))
            payload["history_tip_digest"] = "b" * 64
            (root / "cp-1.json").write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(TrustAnchorError):
                store.retrieve("cp-1")


if __name__ == "__main__":
    unittest.main()
