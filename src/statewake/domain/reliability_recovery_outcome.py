"""Deterministic V1 recovery-outcome binding descriptor."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from statewake.utils.json_support import JsonValue

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
class ReliabilityRecoveryOutcome:
    """Portable binding facts for a successfully recovered reliability outcome.

    This is a semantic descriptor only. The recovery and reconciliation producers remain
    authoritative for their artifacts; this object binds their identities and digests to
    the V1 recovered state without executing or replacing those producers.
    """

    format_version: str
    recovery_id: str
    recovery_digest: str
    recovery_status: str
    source_reconciliation_id: str
    reconciliation_id: str
    reconciliation_digest: str
    reconciliation_status: str
    outcome: str = "recovered"

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if self.format_version != "1":
            raise ValueError("unsupported reliability recovery outcome format version.")
        for name in (
            "recovery_id",
            "source_reconciliation_id",
            "reconciliation_id",
            "recovery_status",
            "reconciliation_status",
            "outcome",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        for name in ("recovery_digest", "reconciliation_digest"):
            _sha256(getattr(self, name), name)
        if self.recovery_status != "applied":
            raise ValueError(
                "reliability recovery outcome requires an applied recovery result."
            )
        if self.reconciliation_status not in {"verified", "recovered"}:
            raise ValueError(
                "reliability recovery outcome requires a verified or recovered reconciliation result."
            )
        if self.outcome != "recovered":
            raise ValueError(
                "reliability recovery outcome must describe a recovered result."
            )
        if self.source_reconciliation_id != self.reconciliation_id:
            raise ValueError(
                "recovery source reconciliation must match the reconciled result identity."
            )

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            "format_version": self.format_version,
            "recovery_id": self.recovery_id,
            "recovery_digest": self.recovery_digest,
            "recovery_status": self.recovery_status,
            "source_reconciliation_id": self.source_reconciliation_id,
            "reconciliation_id": self.reconciliation_id,
            "reconciliation_digest": self.reconciliation_digest,
            "reconciliation_status": self.reconciliation_status,
            "outcome": self.outcome,
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
    def from_dict(cls, payload: Mapping[str, JsonValue]) -> ReliabilityRecoveryOutcome:
        """Construct this object from its serialized dictionary representation."""
        item = cls(
            format_version=str(payload["format_version"]),
            recovery_id=str(payload["recovery_id"]),
            recovery_digest=str(payload["recovery_digest"]),
            recovery_status=str(payload["recovery_status"]),
            source_reconciliation_id=str(payload["source_reconciliation_id"]),
            reconciliation_id=str(payload["reconciliation_id"]),
            reconciliation_digest=str(payload["reconciliation_digest"]),
            reconciliation_status=str(payload["reconciliation_status"]),
            outcome=str(payload.get("outcome", "recovered")),
        )
        supplied = str(payload.get("digest", ""))
        if supplied and supplied != item.digest:
            raise ValueError("reliability recovery outcome digest mismatch.")
        return item
