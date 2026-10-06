"""Adapters implementing external KMS/HSM-style signing boundaries."""

from __future__ import annotations

import base64
import binascii
import json
import subprocess
from collections.abc import Sequence

from ..domain.key_management import (
    KeyLifecycleProvider,
    SigningKeyReference,
    SigningProvider,
)

_EXTERNAL_SIGNING_PROTOCOL = "statewake-external-signing.v1"
_MAX_SIGNER_PAYLOAD_BYTES = 1_048_576
_MAX_SIGNER_RESPONSE_BYTES = 4096


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


class ExternalCommandSigningProvider:
    """Execute a host-managed signer without importing private key material.

    The configured command receives one UTF-8 JSON request on stdin and must emit one
    UTF-8 JSON response on stdout. StateWake never invokes a shell and never passes
    private key material. The signer is responsible for resolving the supplied stable
    key reference inside its own KMS/HSM or other host-controlled custody boundary.
    """

    def __init__(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: float = 30.0,
        max_payload_bytes: int = _MAX_SIGNER_PAYLOAD_BYTES,
        max_response_bytes: int = _MAX_SIGNER_RESPONSE_BYTES,
    ) -> None:
        """Configure the external signer command and bounded execution policy."""
        normalized = tuple(str(part) for part in command)
        if not normalized or any(not part for part in normalized):
            raise ValueError(
                "external signing command must contain non-empty arguments."
            )
        if timeout_seconds <= 0:
            raise ValueError("external signing timeout must be positive.")
        if max_payload_bytes <= 0:
            raise ValueError("external signing payload limit must be positive.")
        if max_response_bytes <= 0:
            raise ValueError("external signing response limit must be positive.")
        self.command = normalized
        self.timeout_seconds = timeout_seconds
        self.max_payload_bytes = max_payload_bytes
        self.max_response_bytes = max_response_bytes

    def sign(self, key: SigningKeyReference, payload: bytes) -> bytes:
        """Request an Ed25519 signature from the configured host signer process."""
        if len(payload) > self.max_payload_bytes:
            raise ValueError("external signing payload exceeds size limit.")
        request = {
            "protocol": _EXTERNAL_SIGNING_PROTOCOL,
            "key": key.to_dict(),
            "payload_base64": base64.urlsafe_b64encode(payload)
            .rstrip(b"=")
            .decode("ascii"),
        }
        request_bytes = (
            json.dumps(
                request,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        try:
            completed = subprocess.run(
                self.command,
                input=request_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("external signing provider timed out.") from exc
        except OSError as exc:
            raise RuntimeError(
                "external signing provider could not be executed."
            ) from exc

        if completed.returncode != 0:
            raise RuntimeError(
                "external signing provider failed with exit code "
                f"{completed.returncode}."
            )
        if len(completed.stdout) > self.max_response_bytes:
            raise ValueError("external signing provider response exceeds size limit.")
        try:
            response = json.loads(completed.stdout.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(
                "external signing provider returned invalid UTF-8 JSON."
            ) from exc
        if not isinstance(response, dict):
            raise ValueError(
                "external signing provider response must be a JSON object."
            )
        required = {"protocol", "algorithm", "key_id", "signature_base64"}
        if set(response) != required:
            raise ValueError(
                "external signing provider response has unsupported fields."
            )
        if response["protocol"] != _EXTERNAL_SIGNING_PROTOCOL:
            raise ValueError("external signing provider protocol mismatch.")
        if response["algorithm"] != key.algorithm:
            raise ValueError("external signing provider algorithm mismatch.")
        if response["key_id"] != key.key_id:
            raise ValueError("external signing provider key identity mismatch.")
        encoded = response["signature_base64"]
        if not isinstance(encoded, str) or not encoded:
            raise ValueError("external signing provider signature must be base64 text.")
        try:
            signature = base64.b64decode(
                encoded + "=" * (-len(encoded) % 4),
                altchars=b"-_",
                validate=True,
            )
        except (binascii.Error, ValueError) as exc:
            raise ValueError(
                "external signing provider signature is not valid base64."
            ) from exc
        if len(signature) != 64:
            raise ValueError(
                "external Ed25519 signature must contain exactly 64 bytes."
            )
        return signature
