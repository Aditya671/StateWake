"""Portable V1 reliability-proof completeness contracts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from statewake.utils.json_support import JsonValue, require_bool, string_sequence


def _canonical(payload: Mapping[str, JsonValue]) -> bytes:
    """Return the canonical representation used for deterministic identity and signing."""
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(value: str) -> bool:
    """Return the SHA-256 digest of the supplied canonical bytes."""
    return len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


@dataclass(frozen=True, slots=True)
class ReliabilityProofCompleteness:
    """Witness that a portable proof contains its full material input set."""

    format_version: str
    proof_format_version: str
    required_proof_artifact_ids: tuple[str, ...]
    required_source_reference_keys: tuple[str, ...]
    material_source_artifact_ids: tuple[str, ...]
    covered_artifact_ids: tuple[str, ...]
    lineage_required: bool
    trust_context_required: bool

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if self.format_version != "1":
            raise ValueError(
                "unsupported reliability proof completeness format version."
            )
        if self.proof_format_version not in {"3"}:
            raise ValueError(
                "unsupported reliability proof format version for completeness witness."
            )
        for field_name in (
            "required_proof_artifact_ids",
            "required_source_reference_keys",
            "material_source_artifact_ids",
            "covered_artifact_ids",
        ):
            values = getattr(self, field_name)
            if any(not value.strip() for value in values):
                raise ValueError(f"{field_name} must not contain blank values.")
            if len(values) != len(set(values)):
                raise ValueError(f"{field_name} must not contain duplicates.")

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            "format_version": self.format_version,
            "proof_format_version": self.proof_format_version,
            "required_proof_artifact_ids": list(self.required_proof_artifact_ids),
            "required_source_reference_keys": list(self.required_source_reference_keys),
            "material_source_artifact_ids": list(self.material_source_artifact_ids),
            "covered_artifact_ids": list(self.covered_artifact_ids),
            "lineage_required": self.lineage_required,
            "trust_context_required": self.trust_context_required,
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
    ) -> ReliabilityProofCompleteness:
        """Construct this object from its serialized dictionary representation."""
        result = cls(
            format_version=str(payload["format_version"]),
            proof_format_version=str(payload["proof_format_version"]),
            required_proof_artifact_ids=string_sequence(
                payload.get("required_proof_artifact_ids", []),
                field="required_proof_artifact_ids",
            ),
            required_source_reference_keys=string_sequence(
                payload.get("required_source_reference_keys", []),
                field="required_source_reference_keys",
            ),
            material_source_artifact_ids=string_sequence(
                payload.get("material_source_artifact_ids", []),
                field="material_source_artifact_ids",
            ),
            covered_artifact_ids=string_sequence(
                payload.get("covered_artifact_ids", []), field="covered_artifact_ids"
            ),
            lineage_required=require_bool(
                payload.get("lineage_required", False), field="lineage_required"
            ),
            trust_context_required=require_bool(
                payload.get("trust_context_required", False),
                field="trust_context_required",
            ),
        )
        supplied = str(payload.get("digest", ""))
        if supplied and (not _sha256(supplied) or supplied != result.digest):
            raise ValueError("reliability proof completeness digest mismatch.")
        return result
