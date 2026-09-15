"""V1 generic reliability-outcome attestations bound to verified evidence and state."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from statewake.utils.json_support import JsonValue, string_sequence

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
class ReliabilityOutcomeAttestation:
    """Immutable proof that one reliability outcome was derived from exact verified inputs."""

    attestation_id: str
    subject_id: str
    occurred_at: str
    actor: str
    evidence_chain_id: str
    evidence_chain_digest: str
    transition_id: str
    transition_digest: str
    reliability_state: str
    decision: str
    verification_status: str
    reconciliation_state: str
    decision_rationale: tuple[str, ...] = ()
    signing_key_id: str | None = None
    previous_digest: str = ""
    digest: str = ""

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        for name, value in (
            ("evidence_chain_digest", self.evidence_chain_digest),
            ("transition_digest", self.transition_digest),
        ):
            _sha256(value, name)
        if self.previous_digest:
            _sha256(self.previous_digest, "previous_digest")
        if (
            not self.attestation_id.strip()
            or not self.subject_id.strip()
            or not self.actor.strip()
        ):
            raise ValueError("attestation_id, subject_id, and actor must not be empty.")
        if self.reliability_state not in {
            "reliable",
            "degraded",
            "unreliable",
            "recovered",
        }:
            raise ValueError("unsupported attested reliability state.")
        if self.decision not in {"accept", "review", "reject"}:
            raise ValueError("decision must be accept, review, or reject.")
        if self.verification_status != "verified":
            raise ValueError(
                "reliability outcome attestation requires verified evidence."
            )
        if self.reconciliation_state not in {"verified", "recovered"}:
            raise ValueError(
                "reliability outcome attestation requires verified or recovered reconciliation state."
            )
        expected = {
            "reliable": "accept",
            "recovered": "accept",
            "degraded": "review",
            "unreliable": "reject",
        }[self.reliability_state]
        if self.decision != expected:
            raise ValueError(
                f"decision {self.decision!r} does not match reliability state {self.reliability_state!r}."
            )
        if (
            self.reliability_state == "recovered"
            and self.reconciliation_state != "recovered"
        ):
            raise ValueError(
                "recovered reliability outcome requires recovered reconciliation state."
            )
        if self.digest and self.digest != self.computed_digest():
            raise ValueError("reliability outcome attestation digest mismatch.")
        object.__setattr__(self, "digest", self.computed_digest())

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            "attestation_id": self.attestation_id,
            "subject_id": self.subject_id,
            "occurred_at": self.occurred_at,
            "actor": self.actor,
            "evidence_chain_id": self.evidence_chain_id,
            "evidence_chain_digest": self.evidence_chain_digest,
            "transition_id": self.transition_id,
            "transition_digest": self.transition_digest,
            "reliability_state": self.reliability_state,
            "decision": self.decision,
            "verification_status": self.verification_status,
            "reconciliation_state": self.reconciliation_state,
            "decision_rationale": list(self.decision_rationale),
            "signing_key_id": self.signing_key_id,
            "previous_digest": self.previous_digest,
        }

    def computed_digest(self) -> str:
        """Digest computed from the canonical payload."""
        return sha256(_canonical(self.payload())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object with an explicit persisted-format marker.

        The marker is serialization metadata and does not enter ``payload()`` or the
        attestation digest, preserving compatibility with existing attestation identities.
        """
        return {"format_version": "1", **self.payload(), "digest": self.digest}

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, JsonValue]
    ) -> ReliabilityOutcomeAttestation:
        """Construct this object from its serialized dictionary representation."""
        format_version = payload.get("format_version")
        if format_version is not None and str(format_version) != "1":
            raise ValueError(
                "unsupported reliability outcome attestation format version."
            )
        return cls(
            attestation_id=str(payload["attestation_id"]),
            subject_id=str(payload["subject_id"]),
            occurred_at=str(payload["occurred_at"]),
            actor=str(payload["actor"]),
            evidence_chain_id=str(payload["evidence_chain_id"]),
            evidence_chain_digest=str(payload["evidence_chain_digest"]),
            transition_id=str(payload["transition_id"]),
            transition_digest=str(payload["transition_digest"]),
            reliability_state=str(payload["reliability_state"]),
            decision=str(payload["decision"]),
            verification_status=str(payload["verification_status"]),
            reconciliation_state=str(payload["reconciliation_state"]),
            decision_rationale=string_sequence(
                payload.get("decision_rationale", []), field="decision_rationale"
            ),
            signing_key_id=None
            if payload.get("signing_key_id") is None
            else str(payload["signing_key_id"]),
            previous_digest=str(payload.get("previous_digest", "")),
            digest=str(payload.get("digest", "")),
        )


@dataclass(frozen=True, slots=True)
class SignedReliabilityOutcomeEnvelope:
    """Ed25519 envelope binding one exact reliability outcome attestation."""

    algorithm: str
    key_id: str
    attestation: dict[str, Any]
    payload_digest: str
    signature: str

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if self.algorithm != "Ed25519":
            raise ValueError("unsupported signature algorithm; expected Ed25519.")
        if not self.key_id.strip():
            raise ValueError("key_id must not be empty.")
        expected = sha256(_canonical(self.attestation)).hexdigest()
        if self.payload_digest != expected:
            raise ValueError(
                "signed reliability outcome payload digest does not match contents."
            )
        if not self.signature.strip():
            raise ValueError("signature must not be empty.")

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {"attestation": self.attestation, "payload_digest": self.payload_digest}

    def payload_bytes(self) -> bytes:
        """Return the canonical payload bytes used for signature verification."""
        return _canonical(self.payload())

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {
            "algorithm": self.algorithm,
            "key_id": self.key_id,
            "attestation": self.attestation,
            "payload_digest": self.payload_digest,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, JsonValue]
    ) -> SignedReliabilityOutcomeEnvelope:
        """Construct this object from its serialized dictionary representation."""
        attestation = payload.get("attestation")
        if not isinstance(attestation, dict):
            raise ValueError("attestation payload must be an object.")
        return cls(
            algorithm=str(payload["algorithm"]),
            key_id=str(payload["key_id"]),
            attestation=dict(attestation),
            payload_digest=str(payload["payload_digest"]),
            signature=str(payload["signature"]),
        )
