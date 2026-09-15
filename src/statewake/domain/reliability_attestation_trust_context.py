"""Portable trust-context contract for signed reliability attestations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from statewake.utils.json_support import JsonValue, require_int

_HEX = set("0123456789abcdef")


def _canonical(payload: Mapping[str, JsonValue]) -> bytes:
    """Return the canonical representation used for deterministic identity and signing."""
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(value: str, field: str) -> None:
    """Return the SHA-256 digest of the supplied canonical bytes."""
    if len(value) != 64 or any(ch not in _HEX for ch in value):
        raise ValueError(f"{field} must be lowercase SHA-256 hex.")


@dataclass(frozen=True, slots=True)
class ReliabilityAttestationTrustContext:
    """Bind a signed outcome to its portable trust context."""

    format_version: str
    envelope_artifact_id: str
    envelope_digest: str
    attestation_id: str
    attestation_digest: str
    signing_key_id: str
    signing_key_digest: str
    trust_state_artifact_id: str
    trust_state_digest: str
    trust_state_version: int
    authority_store_artifact_id: str
    authority_key_id: str
    authority_key_digest: str

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if self.format_version != "1":
            raise ValueError(
                "unsupported reliability attestation trust-context format version."
            )
        for field in (
            "envelope_artifact_id",
            "attestation_id",
            "signing_key_id",
            "trust_state_artifact_id",
            "authority_store_artifact_id",
            "authority_key_id",
        ):
            if not getattr(self, field).strip():
                raise ValueError(f"{field} must not be empty.")
        for field in (
            "envelope_digest",
            "attestation_digest",
            "signing_key_digest",
            "trust_state_digest",
            "authority_key_digest",
        ):
            _sha256(getattr(self, field), field)
        if self.trust_state_version < 1:
            raise ValueError("trust_state_version must be >= 1.")
        ids = {
            self.envelope_artifact_id,
            self.trust_state_artifact_id,
            self.authority_store_artifact_id,
        }
        if len(ids) != 3:
            raise ValueError("trust-context artifact IDs must be unique.")

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            "format_version": self.format_version,
            "envelope_artifact_id": self.envelope_artifact_id,
            "envelope_digest": self.envelope_digest,
            "attestation_id": self.attestation_id,
            "attestation_digest": self.attestation_digest,
            "signing_key_id": self.signing_key_id,
            "signing_key_digest": self.signing_key_digest,
            "trust_state_artifact_id": self.trust_state_artifact_id,
            "trust_state_digest": self.trust_state_digest,
            "trust_state_version": self.trust_state_version,
            "authority_store_artifact_id": self.authority_store_artifact_id,
            "authority_key_id": self.authority_key_id,
            "authority_key_digest": self.authority_key_digest,
        }

    @property
    def digest(self) -> str:
        """Deterministic digest of this object."""
        return sha256(_canonical(self.payload())).hexdigest()

    def to_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        payload = self.payload()
        if include_digest:
            payload["digest"] = self.digest
        return payload

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, JsonValue]
    ) -> ReliabilityAttestationTrustContext:
        """Construct this object from its serialized dictionary representation."""
        context = cls(
            format_version=str(payload["format_version"]),
            envelope_artifact_id=str(payload["envelope_artifact_id"]),
            envelope_digest=str(payload["envelope_digest"]),
            attestation_id=str(payload["attestation_id"]),
            attestation_digest=str(payload["attestation_digest"]),
            signing_key_id=str(payload["signing_key_id"]),
            signing_key_digest=str(payload["signing_key_digest"]),
            trust_state_artifact_id=str(payload["trust_state_artifact_id"]),
            trust_state_digest=str(payload["trust_state_digest"]),
            trust_state_version=require_int(
                payload["trust_state_version"], field="trust_state_version"
            ),
            authority_store_artifact_id=str(payload["authority_store_artifact_id"]),
            authority_key_id=str(payload["authority_key_id"]),
            authority_key_digest=str(payload["authority_key_digest"]),
        )
        supplied = str(payload.get("digest", ""))
        if supplied and supplied != context.digest:
            raise ValueError("reliability attestation trust-context digest mismatch.")
        return context
