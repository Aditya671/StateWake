"""Signed trust lifecycle dedicated to attestation signing keys."""

from __future__ import annotations

import base64
import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol

from statewake.utils.json_support import JsonValue, require_int, require_object
from statewake.utils.signatures import verify_ed25519_signature


def _require_list(value: Any, *, field: str) -> list[Any]:
    """Return a JSON array and reject malformed members rather than dropping them."""
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a JSON array.")
    return value  # type: ignore


def _canonical(payload: Mapping[str, JsonValue]) -> bytes:
    """Return the canonical representation used for deterministic identity and signing."""
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _b64encode(value: bytes) -> str:
    """Encode the value as URL-safe base64 text."""
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    """Decode the URL-safe base64 value and validate its representation."""
    if not isinstance(value, str) or not value:  # type: ignore
        raise ValueError("base64 value must not be empty.")
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, UnicodeEncodeError) as exc:
        raise ValueError("invalid base64 value.") from exc


@dataclass(frozen=True, slots=True)
class AttestationTrustAnchor:
    """One attestation-signing trust anchor with explicit lifecycle status."""

    key_id: str
    public_key: bytes
    status: str = "active"
    superseded_by: str | None = None

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if not self.key_id.strip():
            raise ValueError("key_id must not be empty.")
        if self.status not in {"active", "revoked", "superseded"}:
            raise ValueError("unsupported attestation trust-anchor status.")
        if len(self.public_key) != 32:
            raise ValueError("Ed25519 public key must be 32 bytes.")
        if self.status == "superseded" and not (self.superseded_by or "").strip():
            raise ValueError(
                "superseded attestation trust anchors must identify a replacement key."
            )
        if self.status != "superseded" and self.superseded_by is not None:
            raise ValueError(
                "only superseded attestation trust anchors may declare superseded_by."
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {
            "key_id": self.key_id,
            "public_key": _b64encode(self.public_key),
            "status": self.status,
            "superseded_by": self.superseded_by,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JsonValue]) -> AttestationTrustAnchor:
        """Construct this object from its serialized dictionary representation."""
        return cls(
            key_id=str(payload["key_id"]),
            public_key=_b64decode(str(payload["public_key"])),
            status=str(payload.get("status", "active")),
            superseded_by=None
            if payload.get("superseded_by") is None
            else str(payload["superseded_by"]),
        )


@dataclass(frozen=True, slots=True)
class SignedAttestationTrustState:
    """Immutable signed snapshot of attestation-signing trust state."""

    authority_key_id: str
    version: int
    issued_at: str
    anchors: tuple[AttestationTrustAnchor, ...]
    signature: str
    previous_digest: str | None = None

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if not self.authority_key_id.strip():
            raise ValueError("authority_key_id must not be empty.")
        if self.version < 1:
            raise ValueError("attestation trust state version must be >= 1.")
        if not self.issued_at.strip():
            raise ValueError("issued_at must not be empty.")
        ids = [anchor.key_id for anchor in self.anchors]
        if len(ids) != len(set(ids)):
            raise ValueError("attestation trust state contains duplicate key ids.")
        if not self.signature.strip():
            raise ValueError("signature must not be empty.")
        if self.previous_digest is not None and (
            len(self.previous_digest) != 64
            or any(c not in "0123456789abcdef" for c in self.previous_digest)
        ):
            raise ValueError("previous_digest must be lowercase SHA-256 hex.")
        if any(
            a.status == "superseded"
            and not any(b.key_id == a.superseded_by for b in self.anchors)
            for a in self.anchors
        ):
            raise ValueError(
                "superseded attestation trust anchor references unknown replacement."
            )

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            "authority_key_id": self.authority_key_id,
            "version": self.version,
            "issued_at": self.issued_at,
            "previous_digest": self.previous_digest,
            "anchors": [a.to_dict() for a in self.anchors],
        }

    def payload_bytes(self) -> bytes:
        """Return the canonical payload bytes used for signature verification."""
        return _canonical(self.payload())

    def digest(self) -> str:
        """Deterministic digest of this object."""
        return sha256(self.payload_bytes()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {**self.payload(), "signature": self.signature}

    @classmethod
    def from_dict(cls, payload: Mapping[str, JsonValue]) -> SignedAttestationTrustState:
        """Construct this object from its serialized dictionary representation."""
        return cls(
            authority_key_id=str(payload["authority_key_id"]),
            version=require_int(payload["version"], field="version"),
            issued_at=str(payload["issued_at"]),
            anchors=tuple(
                AttestationTrustAnchor.from_dict(
                    require_object(item, field="anchors[]")
                )
                for item in _require_list(payload.get("anchors", []), field="anchors")
            ),
            signature=str(payload["signature"]),
            previous_digest=None
            if payload.get("previous_digest") is None
            else str(payload["previous_digest"]),
        )


class AttestationTrustStateVerifier(Protocol):
    """Represent the AttestationTrustStateVerifier component of StateWake."""

    def verify(self, state: SignedAttestationTrustState) -> SignedAttestationTrustState:
        """Define the verify protocol operation for this interface."""
        ...


class Ed25519AttestationTrustStateVerifier:
    """Verify attestation trust-state snapshots using a separately trusted authority."""

    def __init__(self, authority_public_keys: Mapping[str, bytes]) -> None:
        """Initialize this component with its configured state."""
        self._authority_public_keys = dict(authority_public_keys)

    def verify(self, state: SignedAttestationTrustState) -> SignedAttestationTrustState:
        """Verify the integrity or validity represented by this object."""
        try:
            raw_key = self._authority_public_keys[state.authority_key_id]
        except KeyError as exc:
            raise ValueError(
                f"unknown attestation trust-state authority key: {state.authority_key_id}"
            ) from exc
        try:
            verify_ed25519_signature(
                raw_key, state.payload_bytes(), _b64decode(state.signature)
            )
        except ValueError as exc:
            raise ValueError(
                "attestation trust-state signature verification failed."
            ) from exc
        return state


def create_signed_attestation_trust_state(
    state: SignedAttestationTrustState,
    *,
    signature: bytes,
    authority_key_id: str | None = None,
) -> SignedAttestationTrustState:
    """Create a signed attestation trust-state snapshot."""
    return SignedAttestationTrustState(
        authority_key_id=authority_key_id or state.authority_key_id,
        version=state.version,
        issued_at=state.issued_at,
        anchors=state.anchors,
        previous_digest=state.previous_digest,
        signature=_b64encode(signature),
    )


def apply_attestation_trust_state(
    state: SignedAttestationTrustState, *, expected_previous_digest: str | None = None
) -> dict[str, str]:
    """Apply and validate an attestation trust-state transition."""
    if state.previous_digest != expected_previous_digest:
        raise ValueError(
            "attestation trust-state previous_digest does not match the current trust-state tip."
        )
    return {anchor.key_id: anchor.status for anchor in state.anchors}


def attestation_signing_key_status(
    state: SignedAttestationTrustState, key_id: str
) -> AttestationTrustAnchor:
    """Return the status of the attestation signing key."""
    for anchor in state.anchors:
        if anchor.key_id == key_id:
            if anchor.status != "active":
                reason = f"attestation signing key {key_id} is {anchor.status}"
                if anchor.superseded_by:
                    reason += f" by {anchor.superseded_by}"
                raise ValueError(reason + ".")
            return anchor
    raise ValueError(f"attestation signing key is not trusted: {key_id}")
