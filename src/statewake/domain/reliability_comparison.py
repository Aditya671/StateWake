"""Canonical behavioral-comparison evidence for the V1 reliability chain."""

from __future__ import annotations

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from statewake.utils.json_support import JsonValue, string_sequence

_HEX64 = set("0123456789abcdef")
_SIGNIFICANCE = {"none", "low", "medium", "high"}


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
class ReliabilityComparisonInput:
    """One immutable source consumed by a canonical behavioral comparison."""

    role: str
    kind: str
    identity: str
    digest: str
    source: str

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        for name in ("role", "kind", "identity", "source"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        _digest(self.digest, "digest")
        if self.source.startswith("/") or ".." in self.source.replace("\\", "/").split(
            "/"
        ):
            raise ValueError("source must be relative and must not contain '..'.")

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {
            "role": self.role,
            "kind": self.kind,
            "identity": self.identity,
            "digest": self.digest,
            "source": self.source.replace("\\", "/"),
        }


@dataclass(frozen=True, slots=True)
class ReliabilityBehavioralComparison:
    """Deterministic, portable comparison evidence derived from the existing BehavioralDiff."""

    comparison_id: str
    before: tuple[ReliabilityComparisonInput, ...]
    after: tuple[ReliabilityComparisonInput, ...]
    diff: dict[str, Any]
    significance: str
    discrepancy: tuple[str, ...]
    digest: str = ""
    format_version: str = "1"

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if self.format_version != "1":
            raise ValueError(
                "unsupported reliability behavioral comparison format version."
            )
        if not self.comparison_id.strip():
            raise ValueError("comparison_id must not be empty.")
        if self.significance not in _SIGNIFICANCE:
            raise ValueError("significance must be one of none, low, medium, high.")
        if not self.before or not self.after:
            raise ValueError(
                "comparison must have at least one before and one after input."
            )
        expected = self.computed_digest()
        if self.digest and self.digest != expected:
            raise ValueError("reliability behavioral comparison digest mismatch.")
        object.__setattr__(self, "digest", expected)
        expected_id = self.computed_comparison_id()
        if self.comparison_id != expected_id:
            raise ValueError("reliability behavioral comparison identity mismatch.")

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            "format_version": self.format_version,
            "before": [item.to_dict() for item in self.before],
            "after": [item.to_dict() for item in self.after],
            "diff": self.diff,
            "significance": self.significance,
            "discrepancy": list(self.discrepancy),
        }

    def computed_comparison_id(self) -> str:
        """Return the deterministic identifier for this behavioral comparison."""
        return sha256(_canonical(self.payload())).hexdigest()

    def computed_digest(self) -> str:
        """Digest computed from the canonical payload."""
        return sha256(_canonical(self.payload())).hexdigest()

    def to_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        payload = {**self.payload(), "comparison_id": self.comparison_id}
        if include_digest:
            payload["digest"] = self.digest
        return payload

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, JsonValue]
    ) -> ReliabilityBehavioralComparison:
        """Construct this object from its serialized dictionary representation."""

        def parse(items: Any) -> tuple[ReliabilityComparisonInput, ...]:
            """Parse the supplied representation into the expected domain object."""
            if not isinstance(items, list):
                raise ValueError("comparison inputs must be arrays.")
            result: list[ReliabilityComparisonInput] = []
            for item in items:
                if not isinstance(item, Mapping):
                    raise ValueError("each comparison input must be a JSON object.")
                result.append(
                    ReliabilityComparisonInput(
                        role=str(item["role"]),
                        kind=str(item["kind"]),
                        identity=str(item["identity"]),
                        digest=str(item["digest"]),
                        source=str(item["source"]),
                    )
                )
            return tuple(result)

        return cls(
            format_version=str(payload.get("format_version", "1")),
            comparison_id=str(payload["comparison_id"]),
            before=parse(payload.get("before", [])),
            after=parse(payload.get("after", [])),
            diff=dict(payload["diff"]),  # type: ignore
            significance=str(payload["significance"]),
            discrepancy=string_sequence(
                payload.get("discrepancy", []), field="discrepancy"
            ),
            digest=str(payload.get("digest", "")),
        )
