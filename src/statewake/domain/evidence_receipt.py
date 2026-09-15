"""Canonical receipts for externally produced reliability evidence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from statewake.utils.json_support import (
    JsonValue,
    require_int,
    string_mapping,
)
from statewake.utils.time import parse_datetime

from .evidence import EvidenceItem
from .reliability_evidence import EvidenceReference

_HEX64 = set("0123456789abcdef")


def _canonical(payload: Mapping[str, JsonValue]) -> bytes:
    """Return the canonical representation used for deterministic identity and signing."""
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _validate_sha256(value: str, name: str) -> None:
    """Validate that the supplied value is a lowercase SHA-256 digest."""
    if len(value) != 64 or any(char not in _HEX64 for char in value):
        raise ValueError(f"{name} must be lowercase SHA-256 hex.")


def _utc_iso(value: datetime) -> str:
    """Return the timestamp in canonical UTC ISO-8601 form."""
    if value.tzinfo is None:
        raise ValueError("captured_at must be timezone-aware.")
    return value.astimezone(UTC).isoformat()


def _empty_string_mapping() -> dict[str, str]:
    """Create an empty string-to-string metadata mapping."""
    return {}


@dataclass(frozen=True, slots=True)
class ExternalEvidenceReceipt:
    """Immutable receipt proving that an external producer supplied one artifact.

    The receipt does not interpret the producer's semantics. It binds producer identity,
    source identity, artifact content, capture time, and optional V1 lineage metadata.
    """

    producer_type: str
    producer_id: str
    artifact_digest: str
    artifact_size: int
    captured_at: datetime
    source_ref: str
    source_event_id: str | None = None
    producer_version: str | None = None
    run_id: str | None = None
    provenance_ref: EvidenceReference | None = None
    metadata: dict[str, str] = field(default_factory=_empty_string_mapping)
    receipt_id: str = ""
    digest: str = ""

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        for name in ("producer_type", "producer_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        if not self.source_ref or not self.source_ref.strip():
            raise ValueError("source_ref must not be empty.")
        if self.producer_version is not None and not self.producer_version.strip():
            raise ValueError("producer_version must not be blank when provided.")
        if self.source_event_id is not None and not self.source_event_id.strip():
            raise ValueError("source_event_id must not be blank when provided.")
        if self.run_id is not None and not self.run_id.strip():
            raise ValueError("run_id must not be blank when provided.")
        _validate_sha256(self.artifact_digest, "artifact_digest")
        if self.artifact_size < 0:
            raise ValueError("artifact_size must be non-negative.")
        _utc_iso(self.captured_at)
        if any(not key.strip() for key in self.metadata):
            raise ValueError("metadata keys must not be blank.")
        if self.provenance_ref is not None and self.provenance_ref.kind != "provenance":
            raise ValueError("provenance_ref must have kind 'provenance'.")
        computed_id = self.computed_receipt_id()
        if self.receipt_id and self.receipt_id != computed_id:
            raise ValueError("receipt_id does not match receipt identity.")
        object.__setattr__(self, "receipt_id", computed_id)
        computed_digest = self.computed_digest()
        if self.digest and self.digest != computed_digest:
            raise ValueError("evidence receipt digest does not match record contents.")
        object.__setattr__(self, "digest", computed_digest)

    def identity_payload(self) -> dict[str, Any]:
        """Return fields defining idempotent producer/artifact identity."""
        return {
            "producer_type": self.producer_type,
            "producer_id": self.producer_id,
            "producer_version": self.producer_version,
            "source_ref": self.source_ref,
            "source_event_id": self.source_event_id,
            "artifact_digest": self.artifact_digest,
            "artifact_size": self.artifact_size,
            "run_id": self.run_id,
            "provenance_ref": None
            if self.provenance_ref is None
            else self.provenance_ref.to_dict(),
            "metadata": dict(sorted(self.metadata.items())),
        }

    def computed_receipt_id(self) -> str:
        """Return a deterministic identity for one producer occurrence.

        A producer-supplied source-event identity is the strongest occurrence key.
        Without one, the stable producer/artifact identity is used.
        """
        identity = (
            {
                "producer_type": self.producer_type,
                "producer_id": self.producer_id,
                "source_event_id": self.source_event_id,
            }
            if self.source_event_id is not None
            else self.identity_payload()
        )
        return sha256(_canonical(identity)).hexdigest()

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            **self.identity_payload(),
            "captured_at": _utc_iso(self.captured_at),
            "receipt_id": self.receipt_id,
        }

    def computed_digest(self) -> str:
        """Digest computed from the canonical payload."""
        return sha256(_canonical(self.payload())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object with an explicit persisted-format marker.

        ``format_version`` is serialization metadata and is intentionally excluded from
        ``payload()`` so existing receipt digests remain stable.
        """
        return {"format_version": "1", **self.payload(), "digest": self.digest}

    def receipt_reference(self, *, source: str | None = None) -> EvidenceReference:
        """Return the canonical producer-occurrence reference for this receipt."""
        return EvidenceReference(
            kind="receipt", identity=self.receipt_id, digest=self.digest, source=source
        )

    def artifact_reference(
        self, *, receipt_source: str | None = None
    ) -> EvidenceReference:
        """Return a V1 evidence-chain reference to the captured artifact.

        When ``receipt_source`` is provided, the evidence reference is explicitly bound
        to this canonical external-evidence receipt.
        """
        return EvidenceReference(
            kind="evidence",
            identity=self.receipt_id,
            digest=self.artifact_digest,
            source=None,
            receipt_ref=None
            if receipt_source is None
            else self.receipt_reference(source=receipt_source),
        )

    def to_evidence_item(self) -> EvidenceItem:
        """Adapt the receipt into the existing V1 evidence-manifest contract."""
        metadata = dict(self.metadata)
        metadata.update(
            {
                "receipt_id": self.receipt_id,
                "producer_type": self.producer_type,
                "producer_id": self.producer_id,
                "source_ref": self.source_ref,
            }
        )
        if self.source_event_id is not None:
            metadata["source_event_id"] = self.source_event_id
        if self.producer_version is not None:
            metadata["producer_version"] = self.producer_version
        if self.run_id is not None:
            metadata["run_id"] = self.run_id
        return EvidenceItem(
            evidence_id=self.receipt_id,
            source=f"{self.producer_type}:{self.producer_id}",
            digest=self.artifact_digest,
            content_ref=f"cas:{self.artifact_digest}",
            metadata=metadata,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, JsonValue]) -> ExternalEvidenceReceipt:
        """Construct this object from its serialized dictionary representation."""
        format_version = payload.get("format_version")
        if format_version is not None and str(format_version) != "1":
            raise ValueError("unsupported external evidence receipt format version.")
        metadata = string_mapping(payload.get("metadata", {}))
        raw_ref = payload.get("provenance_ref")
        provenance_ref = None
        if raw_ref is not None:
            if not isinstance(raw_ref, Mapping):
                raise ValueError("provenance_ref must be a JSON object.")
            provenance_ref = EvidenceReference(
                kind=str(raw_ref["kind"]),
                identity=str(raw_ref["identity"]),
                digest=str(raw_ref["digest"]),
                source=None
                if raw_ref.get("source") is None
                else str(raw_ref["source"]),
            )
        return cls(
            producer_type=str(payload["producer_type"]),
            producer_id=str(payload["producer_id"]),
            artifact_digest=str(payload["artifact_digest"]),
            artifact_size=require_int(payload["artifact_size"], field="artifact_size"),
            captured_at=parse_datetime(
                str(payload["captured_at"]), field="captured_at"
            ),
            source_ref=str(payload["source_ref"]),
            source_event_id=None
            if payload.get("source_event_id") is None
            else str(payload["source_event_id"]),
            producer_version=None
            if payload.get("producer_version") is None
            else str(payload["producer_version"]),
            run_id=None if payload.get("run_id") is None else str(payload["run_id"]),
            provenance_ref=provenance_ref,
            metadata=metadata,
            receipt_id=str(payload.get("receipt_id", "")),
            digest=str(payload.get("digest", "")),
        )
