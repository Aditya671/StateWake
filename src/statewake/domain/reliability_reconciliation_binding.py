"""Deterministic V1 binding between a behavioral discrepancy and its reconciliation result."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from statewake.utils.json_support import JsonValue, string_sequence

_HEX64 = set("0123456789abcdef")


def _canonical(payload: Mapping[str, JsonValue]) -> bytes:
    """Return the canonical representation used for deterministic identity and signing."""
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: str, name: str) -> None:
    """Return the deterministic digest for this domain value."""
    if len(value) != 64 or any(ch not in _HEX64 for ch in value):
        raise ValueError(f"{name} must be lowercase SHA-256 hex.")


@dataclass(frozen=True, slots=True)
class ReliabilityReconciliationBinding:
    """Binds an exact comparison/discrepancy to the exact reconciliation result that resolves it."""

    format_version: str
    comparison_id: str
    comparison_digest: str
    reconciliation_id: str
    reconciliation_digest: str
    reconciliation_status: str
    resolved_discrepancies: tuple[str, ...]
    resolution: str = "resolved"

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if self.format_version != "1":
            raise ValueError(
                "unsupported reliability reconciliation binding format version."
            )
        for name in (
            "comparison_id",
            "reconciliation_id",
            "reconciliation_status",
            "resolution",
        ):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        _digest(self.comparison_digest, "comparison_digest")
        _digest(self.reconciliation_digest, "reconciliation_digest")
        if self.reconciliation_status not in {"verified", "recovered"}:
            raise ValueError(
                "reconciliation binding requires a verified or recovered reconciliation result."
            )
        if self.resolution != "resolved":
            raise ValueError("unsupported reconciliation binding resolution.")
        if any(not item.strip() for item in self.resolved_discrepancies):
            raise ValueError("resolved_discrepancies must not contain blank values.")

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            "format_version": self.format_version,
            "comparison_id": self.comparison_id,
            "comparison_digest": self.comparison_digest,
            "reconciliation_id": self.reconciliation_id,
            "reconciliation_digest": self.reconciliation_digest,
            "reconciliation_status": self.reconciliation_status,
            "resolved_discrepancies": list(self.resolved_discrepancies),
            "resolution": self.resolution,
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
    ) -> ReliabilityReconciliationBinding:
        """Construct this object from its serialized dictionary representation."""
        value = cls(
            format_version=str(payload["format_version"]),
            comparison_id=str(payload["comparison_id"]),
            comparison_digest=str(payload["comparison_digest"]),
            reconciliation_id=str(payload["reconciliation_id"]),
            reconciliation_digest=str(payload["reconciliation_digest"]),
            reconciliation_status=str(payload["reconciliation_status"]),
            resolved_discrepancies=string_sequence(
                payload.get("resolved_discrepancies", []),
                field="resolved_discrepancies",
            ),
            resolution=str(payload.get("resolution", "resolved")),
        )
        supplied = str(payload.get("digest", ""))
        if supplied and supplied != value.digest:
            raise ValueError("reliability reconciliation binding digest mismatch.")
        return value
