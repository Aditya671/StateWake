"""Adapters implementing external KMS/HSM-style signing boundaries."""

from __future__ import annotations

from ..domain.key_management import (
    KeyLifecycleProvider,
    SigningKeyReference,
    SigningProvider,
)


class ExternalSigningAdapter:
    """Reference adapter that delegates signing and key lifecycle to a host provider."""

    def __init__(
        self, provider: SigningProvider, lifecycle: KeyLifecycleProvider | None = None
    ) -> None:
        """Initialize the instance."""
        self.provider = provider
        self.lifecycle = lifecycle

    def sign(self, key: SigningKeyReference, payload: bytes) -> bytes:
        """Sign an attestation through the configured signing provider."""
        signature = self.provider.sign(key, payload)
        if not isinstance(signature, bytes) or not signature:  # type: ignore
            raise ValueError("external signing provider must return non-empty bytes.")
        return signature

    def rotate(self, key: SigningKeyReference) -> SigningKeyReference:
        """Rotate the signing key through the configured key lifecycle provider."""
        if self.lifecycle is None:
            raise RuntimeError("key lifecycle provider is not configured.")
        replacement = self.lifecycle.rotate(key)
        if not isinstance(replacement, SigningKeyReference):  # type: ignore
            raise TypeError("key lifecycle provider must return SigningKeyReference.")
        return replacement

    def revoke(self, key: SigningKeyReference, *, reason: str) -> None:
        """Revoke a signing key through the configured key lifecycle provider."""
        if self.lifecycle is None:
            raise RuntimeError("key lifecycle provider is not configured.")
        if not reason.strip():
            raise ValueError("revocation reason must not be empty.")
        self.lifecycle.revoke(key, reason=reason)
