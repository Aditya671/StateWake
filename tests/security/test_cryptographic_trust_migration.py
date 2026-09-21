"""Regression tests for Tier 15 cryptographic longevity and trust migration."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from typing import cast

from statewake.domain.cryptographic_trust import (
    CryptographicAlgorithm,
    CryptographicKeyIdentity,
    CryptographicProfile,
    KeyStatus,
    ProofFormatMigration,
    TrustMigration,
    retire_key,
    revoke_key,
    rotate_key,
    validate_algorithm_transition,
    validate_historical_verification,
    verify_historical_signature,
)
from statewake.domain.reliability_proof_bundle import (
    ReliabilityProofBundleDescriptor,
    ReliabilityProofSource,
)

ED25519 = CryptographicAlgorithm("Ed25519")
SHA256 = CryptographicAlgorithm("SHA-256")


def key(
    key_id: str, version: int = 1, *, status: KeyStatus = KeyStatus.ACTIVE
) -> CryptographicKeyIdentity:
    """Create a deterministic test key identity."""
    return CryptographicKeyIdentity(
        key_id=key_id,
        version=version,
        algorithm=ED25519,
        public_key_digest=(chr(96 + version) * 64)[:64],
        status=status,
    )


def profile(
    proof: str = "1",
    canonical: str = "1",
    trust: str = "1",
    signature: CryptographicAlgorithm = ED25519,
    digest: CryptographicAlgorithm = SHA256,
) -> CryptographicProfile:
    """Create a deterministic cryptographic profile."""
    return CryptographicProfile(proof, canonical, digest, signature, trust, (proof,))


class _HistoricalVerifier:
    """Record the explicitly supplied historical key used for verification."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, bytes, bytes]] = []

    def verify(
        self, key: CryptographicKeyIdentity, payload: bytes, signature: bytes
    ) -> None:
        self.calls.append((key.key_id, payload, signature))


class TestCryptographicTrustMigration(unittest.TestCase):
    def test_algorithm_identity_is_explicit(self) -> None:
        payload = profile().to_dict()
        signature_algorithm = payload["signature_algorithm"]
        digest_algorithm = payload["digest_algorithm"]
        self.assertIsInstance(signature_algorithm, dict)
        self.assertIsInstance(digest_algorithm, dict)
        self.assertEqual(
            cast(dict[str, object], signature_algorithm)["identifier"], "Ed25519"
        )
        self.assertEqual(
            cast(dict[str, object], digest_algorithm)["identifier"], "SHA-256"
        )

    def test_key_identity_is_versioned(self) -> None:
        self.assertEqual(key("k1").version, 1)
        with self.assertRaises(ValueError):
            key("k1").__class__("k1", 0, ED25519, "a" * 64)

    def test_rotation_supersedes_old_key_without_reactivating_it(self) -> None:
        old, replacement, transition = rotate_key(
            key("old", 1),
            key("new", 2),
            authority="authority-1",
            rationale="cryptoperiod elapsed",
        )
        self.assertEqual(old.status, KeyStatus.SUPERSEDED)
        self.assertEqual(old.successor_key_id, "new")
        self.assertEqual(replacement.status, KeyStatus.ACTIVE)
        self.assertEqual(transition.to_key_id, "new")

    def test_rotation_rejects_algorithm_change(self) -> None:
        replacement = CryptographicKeyIdentity(
            "new", 2, CryptographicAlgorithm("FutureSig"), "b" * 64
        )
        with self.assertRaises(ValueError):
            rotate_key(key("old"), replacement, authority="a", rationale="r")

    def test_retirement_does_not_delete_historical_identity(self) -> None:
        retired, transition = retire_key(
            key("old"), authority="a", rationale="planned retirement"
        )
        self.assertEqual(retired.status, KeyStatus.RETIRED)
        self.assertEqual(retired.key_id, "old")
        self.assertEqual(transition.from_key_id, "old")

    def test_revocation_is_distinct_from_retirement(self) -> None:
        revoked, transition = revoke_key(
            key("old"), authority="a", rationale="compromise"
        )
        self.assertEqual(revoked.status, KeyStatus.REVOKED)
        self.assertEqual(transition.event, KeyStatus.REVOKED)

    def test_historical_verification_accepts_retired_key(self) -> None:
        retired, _ = retire_key(key("old"), authority="a", rationale="old")
        validate_historical_verification(retired, profile())

    def test_historical_signature_uses_retired_key_without_reactivation(self) -> None:
        retired, _ = retire_key(key("old"), authority="a", rationale="old")
        verifier = _HistoricalVerifier()
        verify_historical_signature(
            retired, profile(), b"historical", b"signature", verifier=verifier
        )
        self.assertEqual(verifier.calls, [("old", b"historical", b"signature")])

    def test_historical_verification_rejects_algorithm_mismatch(self) -> None:
        retired, _ = retire_key(key("old"), authority="a", rationale="old")
        with self.assertRaises(ValueError):
            validate_historical_verification(
                retired,
                profile(signature=CryptographicAlgorithm("FutureSig")),
            )

    def test_cryptographic_profile_round_trips_inside_proof_descriptor(self) -> None:
        source = ReliabilityProofSource("run", "run.json", "run-artifact", "a" * 64)
        descriptor = ReliabilityProofBundleDescriptor(
            format_version="1",
            bundle_type="reliability-proof",
            subject_id="subject",
            attestation_artifact_id="attestation",
            evidence_chain_artifact_id="chain",
            state_history_artifact_id="history",
            verification_report_artifact_id="report",
            attestation_id="attestation-id",
            attestation_digest="a" * 64,
            evidence_chain_id="chain-id",
            evidence_chain_digest="b" * 64,
            transition_id="transition-id",
            transition_digest="c" * 64,
            reliability_state="reliable",
            decision="accept",
            verification_report_digest="d" * 64,
            sources=(source,),
            cryptographic_profile=profile(),
        )
        restored = ReliabilityProofBundleDescriptor.from_dict(descriptor.to_dict())
        self.assertEqual(
            restored.cryptographic_profile, descriptor.cryptographic_profile
        )

    def test_proof_format_migration_is_explicit(self) -> None:
        migration = ProofFormatMigration("1", "2", "2", "read-both", "authority")
        self.assertEqual(migration.to_dict()["compatibility_mode"], "read-both")
        with self.assertRaises(ValueError):
            ProofFormatMigration("1", "1", "2", "read-both", "authority")

    def test_trust_migration_is_versioned(self) -> None:
        migration = TrustMigration(
            "m1",
            "root-1",
            1,
            "root-2",
            2,
            "authority",
            "activation-2",
            "policy-2",
        )
        self.assertEqual(migration.to_dict()["to_root_version"], 2)

    def test_profile_transition_requires_explicit_trust_migration(self) -> None:
        old = profile("1", "1", "1")
        new = profile("2", "2", "2")
        with self.assertRaises(ValueError):
            validate_algorithm_transition(old, new, migration=None)

    def test_profile_transition_rejects_unannounced_canonicalization_change(
        self,
    ) -> None:
        old = profile("1", "1", "1")
        new = profile("1", "2", "1")
        with self.assertRaises(ValueError):
            validate_algorithm_transition(old, new, migration=None)

    def test_profile_transition_accepts_versioned_migration(self) -> None:
        old = profile("1", "1", "1")
        new = profile("2", "2", "2")
        migration = TrustMigration(
            "m1",
            "root-1",
            1,
            "root-2",
            2,
            "authority",
            "activation-2",
            "policy-2",
        )
        validate_algorithm_transition(old, new, migration=migration)

    def test_mixed_version_verifier_compatibility_is_declared(self) -> None:
        payload = CryptographicProfile(
            "2", "2", SHA256, ED25519, "2", ("1", "2")
        ).to_dict()
        self.assertEqual(payload["verifier_compatibility"], ["1", "2"])

    def test_portable_cryptographic_trust_verifier_runs(self) -> None:
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            [
                sys.executable,
                str(root / "scripts/security/verify_cryptographic_trust_migration.py"),
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            env={**__import__("os").environ, "PYTHONPATH": str(root / "src")},
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


if __name__ == "__main__":
    unittest.main()
