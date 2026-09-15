"""Loading and verification helpers for reliability attestation trust state."""

from __future__ import annotations

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
import base64
from collections.abc import Mapping
from pathlib import Path

from statewake.utils.json_support import load_object

from ..domain.attestation_trust import (
    Ed25519AttestationTrustStateVerifier,
    SignedAttestationTrustState,
)


def load_authority_store(path: Path) -> dict[str, bytes]:
    """Load externally managed verification keys from an authority-store document."""
    payload = load_object(path)
    if not isinstance(payload, dict) or not isinstance(payload.get("keys", {}), dict):
        raise ValueError("authority store must contain a keys object.")

    result: dict[str, bytes] = {}
    for key_id, encoded in payload["keys"].items():  # type: ignore
        if not isinstance(encoded, str):
            raise ValueError(f"authority key {key_id!r} must be base64 text.")
        result[str(key_id)] = base64.urlsafe_b64decode(
            encoded + "=" * (-len(encoded) % 4)
        )
    return result


def load_attestation_trust_state(path: Path) -> SignedAttestationTrustState:
    """Load a serialized reliability-attestation trust state."""
    payload = load_object(path)
    if not isinstance(payload, dict):
        raise ValueError("attestation trust-state root must be an object.")
    return SignedAttestationTrustState.from_dict(payload)


def verify_attestation_trust_state(
    path: Path,
    authority_store: Mapping[str, bytes],
) -> SignedAttestationTrustState:
    """Verify an attestation trust state against the supplied trust anchors."""
    state = load_attestation_trust_state(path)
    return Ed25519AttestationTrustStateVerifier(authority_store).verify(state)
