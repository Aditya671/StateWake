"""Versioned cryptographic and trust-migration contracts for StateWake."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

_HEX = set("0123456789abcdef")


class KeyStatus(StrEnum):
    """Lifecycle state for a cryptographic key identity."""

    ACTIVE = "active"
    RETIRED = "retired"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class CryptographicAlgorithm:
    """Explicit identifier and parameter contract for one algorithm."""

    identifier: str
    parameters: str = ""

    def __post_init__(self) -> None:
        """Validate Existence."""
        if not self.identifier.strip():
            raise ValueError("algorithm identifier must not be empty.")
        if "\n" in self.identifier or "\r" in self.identifier:
            raise ValueError("algorithm identifier must be single-line.")

    def to_dict(self) -> dict[str, str]:
        """Serialize the algorithm identity."""
        return {"identifier": self.identifier, "parameters": self.parameters}


@dataclass(frozen=True, slots=True)
class CryptographicKeyIdentity:
    """Stable key identity whose private material remains outside StateWake."""

    key_id: str
    version: int
    algorithm: CryptographicAlgorithm
    public_key_digest: str
    status: KeyStatus = KeyStatus.ACTIVE
    successor_key_id: str | None = None

    def __post_init__(self) -> None:
        """Validate Existence."""
        if not self.key_id.strip():
            raise ValueError("key_id must not be empty.")
        if self.version < 1:
            raise ValueError("key version must be >= 1.")
        if len(self.public_key_digest) != 64 or any(
            char not in _HEX for char in self.public_key_digest
        ):
            raise ValueError("public_key_digest must be lowercase SHA-256 hex.")
        if (
            self.status is KeyStatus.SUPERSEDED
            and not (self.successor_key_id or "").strip()
        ):
            raise ValueError("superseded key must identify a successor key.")
        if (
            self.status is not KeyStatus.SUPERSEDED
            and self.successor_key_id is not None
        ):
            raise ValueError("only superseded keys may identify successor_key_id.")

    def to_dict(self) -> dict[str, object]:
        """Serialize the key identity."""
        return {
            "key_id": self.key_id,
            "version": self.version,
            "algorithm": self.algorithm.to_dict(),
            "public_key_digest": self.public_key_digest,
            "status": self.status.value,
            "successor_key_id": self.successor_key_id,
        }


@dataclass(frozen=True, slots=True)
class CryptographicProfile:
    """Versioned cryptographic contract carried by portable evidence."""

    proof_schema_version: str
    canonicalization_version: str
    digest_algorithm: CryptographicAlgorithm
    signature_algorithm: CryptographicAlgorithm
    trust_policy_version: str
    verifier_compatibility: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate Existence."""
        for name in (
            "proof_schema_version",
            "canonicalization_version",
            "trust_policy_version",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        if not self.verifier_compatibility:
            raise ValueError("verifier_compatibility must not be empty.")
        if any(not item.strip() for item in self.verifier_compatibility):
            raise ValueError("verifier compatibility identifiers must not be empty.")

    def to_dict(self) -> dict[str, object]:
        """Serialize the versioned cryptographic contract."""
        return {
            "proof_schema_version": self.proof_schema_version,
            "canonicalization_version": self.canonicalization_version,
            "digest_algorithm": self.digest_algorithm.to_dict(),
            "signature_algorithm": self.signature_algorithm.to_dict(),
            "trust_policy_version": self.trust_policy_version,
            "verifier_compatibility": list(self.verifier_compatibility),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> CryptographicProfile:
        """Construct a cryptographic profile from its explicit serialized form."""
        digest = payload.get("digest_algorithm")
        signature = payload.get("signature_algorithm")
        compatibility = payload.get("verifier_compatibility")
        if not isinstance(digest, Mapping) or not isinstance(signature, Mapping):
            raise ValueError("cryptographic algorithm objects must be mappings.")
        if not isinstance(compatibility, list) or not all(
            isinstance(item, str) for item in compatibility
        ):
            raise ValueError("verifier_compatibility must be a string array.")
        return cls(
            proof_schema_version=str(payload["proof_schema_version"]),
            canonicalization_version=str(payload["canonicalization_version"]),
            digest_algorithm=CryptographicAlgorithm(
                str(digest["identifier"]), str(digest.get("parameters", ""))
            ),
            signature_algorithm=CryptographicAlgorithm(
                str(signature["identifier"]),
                str(signature.get("parameters", "")),
            ),
            trust_policy_version=str(payload["trust_policy_version"]),
            verifier_compatibility=tuple(compatibility),
        )


@dataclass(frozen=True, slots=True)
class KeyLifecycleTransition:
    """Auditable change from one key identity to another lifecycle state."""

    from_key_id: str
    to_key_id: str
    event: KeyStatus
    rationale: str
    authority: str

    def __post_init__(self) -> None:
        """Validate Existence."""
        for name in ("from_key_id", "to_key_id", "rationale", "authority"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        if self.event not in {
            KeyStatus.RETIRED,
            KeyStatus.REVOKED,
            KeyStatus.SUPERSEDED,
        }:
            raise ValueError(
                "key transition event must be retired, revoked, or superseded."
            )

    def to_dict(self) -> dict[str, str]:
        """Serialize the lifecycle transition."""
        return {
            "from_key_id": self.from_key_id,
            "to_key_id": self.to_key_id,
            "event": self.event.value,
            "rationale": self.rationale,
            "authority": self.authority,
        }


@dataclass(frozen=True, slots=True)
class TrustMigration:
    """Evidence-backed transition between versioned trust roots."""

    migration_id: str
    from_root_id: str
    from_root_version: int
    to_root_id: str
    to_root_version: int
    transition_authority: str
    activation_boundary: str
    verification_policy_version: str

    def __post_init__(self) -> None:
        """Validate Existence."""
        for name in (
            "migration_id",
            "from_root_id",
            "to_root_id",
            "transition_authority",
            "activation_boundary",
            "verification_policy_version",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        if self.from_root_version < 1 or self.to_root_version < 1:
            raise ValueError("trust-root versions must be >= 1.")
        if (self.from_root_id, self.from_root_version) == (
            self.to_root_id,
            self.to_root_version,
        ):
            raise ValueError(
                "trust migration must change the trust root version or identity."
            )

    def to_dict(self) -> dict[str, object]:
        """Serialize the trust migration contract."""
        return {
            "migration_id": self.migration_id,
            "from_root_id": self.from_root_id,
            "from_root_version": self.from_root_version,
            "to_root_id": self.to_root_id,
            "to_root_version": self.to_root_version,
            "transition_authority": self.transition_authority,
            "activation_boundary": self.activation_boundary,
            "verification_policy_version": self.verification_policy_version,
        }


@dataclass(frozen=True, slots=True)
class ProofFormatMigration:
    """Explicit migration semantics between portable proof schema versions."""

    from_version: str
    to_version: str
    canonicalization_version: str
    compatibility_mode: str
    migration_authority: str

    def __post_init__(self) -> None:
        """Validate ProofFormatMigration."""
        for name in (
            "from_version",
            "to_version",
            "canonicalization_version",
            "compatibility_mode",
            "migration_authority",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        if self.from_version == self.to_version:
            raise ValueError("proof format migration must change versions.")
        if self.compatibility_mode not in {
            "read-both",
            "rewrite-forward",
            "dual-format",
        }:
            raise ValueError("unsupported proof-format compatibility mode.")

    def to_dict(self) -> dict[str, str]:
        """Serialize proof-format migration semantics."""
        return {
            "from_version": self.from_version,
            "to_version": self.to_version,
            "canonicalization_version": self.canonicalization_version,
            "compatibility_mode": self.compatibility_mode,
            "migration_authority": self.migration_authority,
        }


class HistoricalSignatureVerifier(Protocol):
    """Verify a historical signature without making the retired key active again."""

    def verify(
        self, key: CryptographicKeyIdentity, payload: bytes, signature: bytes
    ) -> None:
        """Verify a signature using the explicitly identified historical key."""
        ...


def rotate_key(
    current: CryptographicKeyIdentity,
    replacement: CryptographicKeyIdentity,
    *,
    authority: str,
    rationale: str,
) -> tuple[CryptographicKeyIdentity, CryptographicKeyIdentity, KeyLifecycleTransition]:
    """Create an auditable key rotation without reactivating the old key."""
    if current.status is not KeyStatus.ACTIVE:
        raise ValueError("only an active key may be rotated.")
    if replacement.status is not KeyStatus.ACTIVE:
        raise ValueError("replacement key must be active.")
    if replacement.key_id == current.key_id:
        raise ValueError("replacement key must have a new identity.")
    if replacement.algorithm != current.algorithm:
        raise ValueError("key rotation cannot silently change algorithms.")
    if replacement.version <= current.version:
        raise ValueError("replacement key version must increase.")
    successor = CryptographicKeyIdentity(
        key_id=current.key_id,
        version=current.version,
        algorithm=current.algorithm,
        public_key_digest=current.public_key_digest,
        status=KeyStatus.SUPERSEDED,
        successor_key_id=replacement.key_id,
    )
    transition = KeyLifecycleTransition(
        from_key_id=current.key_id,
        to_key_id=replacement.key_id,
        event=KeyStatus.SUPERSEDED,
        rationale=rationale,
        authority=authority,
    )
    return successor, replacement, transition


def retire_key(
    key: CryptographicKeyIdentity, *, authority: str, rationale: str
) -> tuple[CryptographicKeyIdentity, KeyLifecycleTransition]:
    """Retire a key for new signing while preserving its historical identity."""
    if key.status is not KeyStatus.ACTIVE:
        raise ValueError("only an active key may be retired.")
    retired = CryptographicKeyIdentity(
        key_id=key.key_id,
        version=key.version,
        algorithm=key.algorithm,
        public_key_digest=key.public_key_digest,
        status=KeyStatus.RETIRED,
    )
    return retired, KeyLifecycleTransition(
        from_key_id=key.key_id,
        to_key_id=key.key_id,
        event=KeyStatus.RETIRED,
        rationale=rationale,
        authority=authority,
    )


def revoke_key(
    key: CryptographicKeyIdentity, *, authority: str, rationale: str
) -> tuple[CryptographicKeyIdentity, KeyLifecycleTransition]:
    """Revoke a key without deleting its historical identity."""
    if key.status is KeyStatus.REVOKED:
        return key, KeyLifecycleTransition(
            from_key_id=key.key_id,
            to_key_id=key.key_id,
            event=KeyStatus.REVOKED,
            rationale=rationale,
            authority=authority,
        )
    revoked = CryptographicKeyIdentity(
        key_id=key.key_id,
        version=key.version,
        algorithm=key.algorithm,
        public_key_digest=key.public_key_digest,
        status=KeyStatus.REVOKED,
        successor_key_id=None,
    )
    return revoked, KeyLifecycleTransition(
        from_key_id=key.key_id,
        to_key_id=key.key_id,
        event=KeyStatus.REVOKED,
        rationale=rationale,
        authority=authority,
    )


def verify_historical_signature(
    key: CryptographicKeyIdentity,
    profile: CryptographicProfile,
    payload: bytes,
    signature: bytes,
    *,
    verifier: HistoricalSignatureVerifier,
) -> None:
    """Verify historical evidence with an explicitly identified retired key."""
    validate_historical_verification(key, profile)
    verifier.verify(key, payload, signature)


def validate_historical_verification(
    key: CryptographicKeyIdentity,
    profile: CryptographicProfile,
) -> None:
    """Ensure a retired/revoked key remains interpretable for historical evidence."""
    if key.status not in {
        KeyStatus.RETIRED,
        KeyStatus.REVOKED,
        KeyStatus.SUPERSEDED,
    }:
        raise ValueError(
            "historical verification requires a non-active historical key."
        )
    if key.algorithm.identifier != profile.signature_algorithm.identifier:
        raise ValueError(
            "historical signature algorithm does not match the evidence profile."
        )


def validate_algorithm_transition(
    old: CryptographicProfile,
    new: CryptographicProfile,
    *,
    migration: TrustMigration | None,
) -> None:
    """Validate a deliberate cryptographic migration with explicit version semantics."""
    if old.proof_schema_version == new.proof_schema_version and (
        old.canonicalization_version == new.canonicalization_version
        and old.digest_algorithm == new.digest_algorithm
        and old.signature_algorithm == new.signature_algorithm
        and old.trust_policy_version == new.trust_policy_version
    ):
        raise ValueError("new cryptographic profile is identical to the old profile.")
    if (
        old.canonicalization_version != new.canonicalization_version
        and old.proof_schema_version == new.proof_schema_version
    ):
        raise ValueError(
            "canonicalization changes require an explicit proof-schema transition."
        )
    if old.trust_policy_version != new.trust_policy_version and migration is None:
        raise ValueError("trust-policy changes require an explicit trust migration.")
    if old.signature_algorithm != new.signature_algorithm and migration is None:
        raise ValueError(
            "signature-algorithm changes require an explicit trust migration."
        )
    if old.digest_algorithm != new.digest_algorithm and migration is None:
        raise ValueError(
            "digest-algorithm changes require an explicit trust migration."
        )
