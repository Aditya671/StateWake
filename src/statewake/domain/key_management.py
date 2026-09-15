"""Framework-neutral key-management boundaries for attestation signing."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SigningKeyReference:
    """Stable reference to a remotely managed signing key; private material never enters StateWake."""

    key_id: str
    provider: str
    algorithm: str = "Ed25519"
    version: str | None = None
    public_key_digest: str | None = None

    def __post_init__(self) -> None:
        """Validate and normalize the instance after initialization."""
        if not self.key_id.strip() or not self.provider.strip():
            raise ValueError("key_id and provider must not be empty.")
        if self.algorithm != "Ed25519":
            raise ValueError("unsupported signing algorithm; expected Ed25519.")
        if self.public_key_digest is not None and (
            len(self.public_key_digest) != 64
            or any(c not in "0123456789abcdef" for c in self.public_key_digest)
        ):
            raise ValueError("public_key_digest must be lowercase SHA-256 hex.")

    def to_dict(self) -> dict[str, str | None]:
        """Serialize this object to a dictionary."""
        return {
            "key_id": self.key_id,
            "provider": self.provider,
            "algorithm": self.algorithm,
            "version": self.version,
            "public_key_digest": self.public_key_digest,
        }


class SigningProvider(Protocol):
    """External signer boundary. StateWake supplies bytes and receives a signature."""

    def sign(self, key: SigningKeyReference, payload: bytes) -> bytes:
        """Sign payload bytes using an externally managed private key."""
        ...


class KeyLifecycleProvider(Protocol):
    """Host-facing key lifecycle operations for rotation and revocation."""

    def rotate(self, key: SigningKeyReference) -> SigningKeyReference:
        """Return the replacement public key reference."""
        ...

    def revoke(self, key: SigningKeyReference, *, reason: str) -> None:
        """Revoke the referenced signing key."""
        ...


def public_key_digest(public_key: bytes) -> str:
    """Compute the portable digest used to bind an external trust anchor to a key."""
    return sha256(public_key).hexdigest()
