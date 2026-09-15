"""Deterministic semantic decision-basis binding for the V1 reliability outcome."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from statewake.utils.json_support import JsonValue, string_sequence

_DECISIONS = {"accept", "review", "reject"}
_STATES = {"reliable", "degraded", "unreliable", "recovered"}
_HEX = set("0123456789abcdef")


def _canonical(payload: Mapping[str, JsonValue]) -> bytes:
    """Return the canonical representation used for deterministic identity and signing."""
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(value: str, field: str) -> None:
    """Return the SHA-256 digest of the supplied canonical bytes."""
    if len(value) != 64 or any(char not in _HEX for char in value):
        raise ValueError(f"{field} must be lowercase SHA-256 hex.")


@dataclass(frozen=True, slots=True)
class ReliabilityDecisionBasis:
    """Immutable semantic claim describing the exact basis used for a reliability decision.

    This is a binding/verification contract, not a policy evaluator.  The referenced
    artifact remains authoritative; the engine verifies its identity, integrity, and
    consistency with the recorded reliability decision semantics.
    """

    format_version: str
    basis_type: str
    basis_id: str
    version: str
    decision: str
    reliability_state: str
    rationale: tuple[str, ...] = ()
    input_digests: tuple[str, ...] = ()
    policy_id: str | None = None
    policy_version: str | None = None
    policy_digest: str | None = None
    digest: str = ""

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if self.format_version != "1":
            raise ValueError("unsupported reliability decision basis format version.")
        if self.basis_type not in {
            "policy",
            "rule",
            "comparison",
            "manual",
            "external",
        }:
            raise ValueError("unsupported reliability decision basis type.")
        for name in ("basis_id", "version"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        if self.decision not in _DECISIONS:
            raise ValueError("unsupported decision in reliability decision basis.")
        if self.reliability_state not in _STATES:
            raise ValueError(
                "unsupported reliability state in reliability decision basis."
            )
        expected = {
            "accept": {"reliable", "recovered"},
            "review": {"degraded"},
            "reject": {"unreliable"},
        }[self.decision]
        if self.reliability_state not in expected:
            raise ValueError(
                "decision/state semantics do not agree in reliability decision basis."
            )
        for item in self.input_digests:
            _sha256(item, "input_digests item")
        if self.policy_digest is not None:
            _sha256(self.policy_digest, "policy_digest")
            if self.basis_type != "policy":
                raise ValueError(
                    "policy_digest is only valid for policy decision bases."
                )
        if self.policy_id is not None and not self.policy_id.strip():
            raise ValueError("policy_id must not be blank when provided.")
        if self.policy_version is not None and not self.policy_version.strip():
            raise ValueError("policy_version must not be blank when provided.")
        computed = self.computed_digest()
        if self.digest and self.digest != computed:
            raise ValueError("reliability decision basis digest mismatch.")
        object.__setattr__(self, "digest", computed)

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            "format_version": self.format_version,
            "basis_type": self.basis_type,
            "basis_id": self.basis_id,
            "version": self.version,
            "decision": self.decision,
            "reliability_state": self.reliability_state,
            "rationale": list(self.rationale),
            "input_digests": list(self.input_digests),
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "policy_digest": self.policy_digest,
        }

    def computed_digest(self) -> str:
        """Digest computed from the canonical payload."""
        return sha256(_canonical(self.payload())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_dict(cls, payload: Mapping[str, JsonValue]) -> ReliabilityDecisionBasis:
        """Construct this object from its serialized dictionary representation."""
        return cls(
            format_version=str(payload["format_version"]),
            basis_type=str(payload["basis_type"]),
            basis_id=str(payload["basis_id"]),
            version=str(payload["version"]),
            decision=str(payload["decision"]),
            reliability_state=str(payload["reliability_state"]),
            rationale=string_sequence(payload.get("rationale", []), field="rationale"),
            input_digests=string_sequence(
                payload.get("input_digests", []), field="input_digests"
            ),
            policy_id=None
            if payload.get("policy_id") is None
            else str(payload["policy_id"]),
            policy_version=None
            if payload.get("policy_version") is None
            else str(payload["policy_version"]),
            policy_digest=None
            if payload.get("policy_digest") is None
            else str(payload["policy_digest"]),
            digest=str(payload.get("digest", "")),
        )
