"""Typed cryptographic signature helpers for StateWake."""

from __future__ import annotations


def verify_ed25519_signature(
    public_key: bytes,
    message: bytes,
    signature: bytes,
) -> None:
    """Verify an Ed25519 signature using the PyNaCl implementation.

    Args:
        public_key: The raw 32-byte Ed25519 public key.
        message: The exact bytes that were signed.
        signature: The raw 64-byte Ed25519 signature.

    Raises:
        ValueError: If the key or signature is malformed, or verification fails.
        RuntimeError: If PyNaCl is not installed in the runtime environment.

    """
    try:
        from nacl.exceptions import BadSignatureError
        from nacl.signing import VerifyKey
    except ImportError as exc:
        raise RuntimeError(
            "Ed25519 signature verification requires the declared 'PyNaCl' package."
        ) from exc

    try:
        VerifyKey(public_key).verify(message, signature)
    except (ValueError, BadSignatureError) as exc:
        raise ValueError("Ed25519 signature verification failed.") from exc
