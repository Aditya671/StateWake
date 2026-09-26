"""Portable verifier for Tier 15 cryptographic/trust-migration semantics."""

from __future__ import annotations

from statewake.domain.cryptographic_trust import (
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
