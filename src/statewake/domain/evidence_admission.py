"""Deterministic admission contracts for externally produced reliability evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from statewake.utils.json_support import JsonValue, require_int

from .reliability_evidence import EvidenceReference


def _canonical(payload: Mapping[str, JsonValue]) -> bytes:
    """Return the canonical representation used for deterministic identity and signing."""
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class ExternalEvidenceAdmission:
    """A deterministic proof that one external receipt is admissible to the V1 model."""

    receipt_id: str
    receipt_digest: str
    artifact_digest: str
    artifact_size: int
    producer_type: str
    producer_id: str
    source_event_id: str | None
    run_id: str | None
    evidence_reference: EvidenceReference

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        for name in (
            "receipt_id",
            "receipt_digest",
            "artifact_digest",
            "producer_type",
            "producer_id",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        for name in ("receipt_digest", "artifact_digest"):
            value = getattr(self, name)
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                raise ValueError(f"{name} must be lowercase SHA-256 hex.")
        if self.artifact_size < 0:
            raise ValueError("artifact_size must be non-negative.")
        if self.evidence_reference.kind != "evidence":
            raise ValueError("evidence_reference must have kind 'evidence'.")
        if self.evidence_reference.receipt_ref is None:
            raise ValueError(
                "evidence_reference must retain its canonical receipt binding."
            )
        if self.evidence_reference.receipt_ref.identity != self.receipt_id:
            raise ValueError(
                "evidence_reference receipt identity does not match admission."
            )
        if self.evidence_reference.receipt_ref.digest != self.receipt_digest:
            raise ValueError(
                "evidence_reference receipt digest does not match admission."
            )
        if self.evidence_reference.digest != self.artifact_digest:
            raise ValueError(
                "evidence_reference artifact digest does not match admission."
            )

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            "receipt_id": self.receipt_id,
            "receipt_digest": self.receipt_digest,
            "artifact_digest": self.artifact_digest,
            "artifact_size": self.artifact_size,
            "producer_type": self.producer_type,
            "producer_id": self.producer_id,
            "source_event_id": self.source_event_id,
            "run_id": self.run_id,
            "evidence_reference": self.evidence_reference.to_dict(),
        }

    @property
    def digest(self) -> str:
        """Deterministic digest of this object."""
        return sha256(_canonical(self.payload())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_dict(cls, payload: Mapping[str, JsonValue]) -> ExternalEvidenceAdmission:
        """Construct this object from its serialized dictionary representation."""
        raw_ref = payload.get("evidence_reference")
        if not isinstance(raw_ref, Mapping):
            raise ValueError("evidence_reference must be an object.")
        raw_receipt = raw_ref.get("receipt_ref")
        if not isinstance(raw_receipt, Mapping):
            raise ValueError("evidence_reference.receipt_ref must be an object.")
        receipt_ref = EvidenceReference(
            kind=str(raw_receipt["kind"]),
            identity=str(raw_receipt["identity"]),
            digest=str(raw_receipt["digest"]),
            source=None
            if raw_receipt.get("source") is None
            else str(raw_receipt["source"]),
        )
        evidence_ref = EvidenceReference(
            kind=str(raw_ref["kind"]),
            identity=str(raw_ref["identity"]),
            digest=str(raw_ref["digest"]),
            source=None if raw_ref.get("source") is None else str(raw_ref["source"]),
            receipt_ref=receipt_ref,
        )
        item = cls(
            receipt_id=str(payload["receipt_id"]),
            receipt_digest=str(payload["receipt_digest"]),
            artifact_digest=str(payload["artifact_digest"]),
            artifact_size=require_int(payload["artifact_size"], field="artifact_size"),
            producer_type=str(payload["producer_type"]),
            producer_id=str(payload["producer_id"]),
            source_event_id=None
            if payload.get("source_event_id") is None
            else str(payload["source_event_id"]),
            run_id=None if payload.get("run_id") is None else str(payload["run_id"]),
            evidence_reference=evidence_ref,
        )
        supplied = str(payload.get("digest", ""))
        if supplied and supplied != item.digest:
            raise ValueError("external evidence admission digest mismatch.")
        return item
