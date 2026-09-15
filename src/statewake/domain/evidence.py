"""Evidence records and manifests supporting agent decisions."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from statewake.utils.json_support import (
    JsonValue,
    require_object,
    string_mapping,
)


def _empty_string_mapping() -> dict[str, str]:
    """Create an empty string-to-string metadata mapping."""
    return {}


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    """A reference to evidence available to an agent at decision time."""

    evidence_id: str
    source: str
    digest: str | None = None
    content_ref: str | None = None
    metadata: dict[str, str] = field(default_factory=_empty_string_mapping)
    sensitivity: str = "internal"

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if not self.evidence_id.strip():
            raise ValueError("evidence_id must not be empty.")
        if not self.source.strip():
            raise ValueError("source must not be empty.")
        if self.digest is None and self.content_ref is None:
            raise ValueError("Evidence must have a digest or content_ref.")
        if self.sensitivity not in {"public", "internal", "confidential", "restricted"}:
            raise ValueError(
                "sensitivity must be one of public, internal, confidential, restricted."
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "digest": self.digest,
            "content_ref": self.content_ref,
            "metadata": dict(sorted(self.metadata.items())),
            "sensitivity": self.sensitivity,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JsonValue]) -> "EvidenceItem":
        """Construct this object from its serialized dictionary representation."""
        missing = [key for key in ("evidence_id", "source") if key not in payload]
        if missing:
            raise ValueError(f"Missing required evidence fields: {', '.join(missing)}")
        metadata = string_mapping(payload.get("metadata", {}))
        return cls(
            evidence_id=str(payload["evidence_id"]),
            source=str(payload["source"]),
            digest=None if payload.get("digest") is None else str(payload["digest"]),
            content_ref=(
                None
                if payload.get("content_ref") is None
                else str(payload["content_ref"])
            ),
            metadata=metadata,
            sensitivity=str(payload.get("sensitivity", "internal")),
        )


@dataclass(frozen=True, slots=True)
class EvidenceManifest:
    """Immutable collection of evidence references for one run or decision."""

    manifest_id: str
    run_id: str
    items: tuple[EvidenceItem, ...] = ()

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if not self.manifest_id.strip():
            raise ValueError("manifest_id must not be empty.")
        if not self.run_id.strip():
            raise ValueError("run_id must not be empty.")
        ids = [item.evidence_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Evidence IDs must be unique within a manifest.")

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {
            "manifest_id": self.manifest_id,
            "run_id": self.run_id,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JsonValue]) -> "EvidenceManifest":
        """Construct this object from its serialized dictionary representation."""
        items = payload.get("items", [])
        if not isinstance(items, list):
            raise ValueError("items must be a JSON array.")
        return cls(
            manifest_id=str(payload.get("manifest_id", "")),
            run_id=str(payload.get("run_id", "")),
            items=tuple(EvidenceItem.from_dict(require_object(item)) for item in items),
        )
