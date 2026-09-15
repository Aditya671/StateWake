"""System-state snapshot primitives and deterministic fingerprinting."""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from statewake.utils.json_support import JsonValue
from statewake.utils.time import parse_datetime


def _canonical_json(payload: Mapping[str, JsonValue]) -> bytes:
    """Return the canonical JSON representation used for deterministic hashing."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _empty_string_mapping() -> dict[str, str]:
    """Create an empty string-to-string mapping for tool digests."""
    return {}


@dataclass(frozen=True, slots=True)
class SystemState:
    """Immutable description of relevant runtime state for a run."""

    state_id: str
    captured_at: datetime
    agent_version: str
    model: str
    prompt_digest: str
    tool_digests: dict[str, str] = field(default_factory=_empty_string_mapping)
    retrieval_digest: str | None = None
    memory_digest: str | None = None
    policy_digest: str | None = None

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if not self.state_id.strip():
            raise ValueError("state_id must not be empty.")
        if self.captured_at.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware.")
        for name in ("agent_version", "model", "prompt_digest"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        if any(
            not name.strip() or not digest.strip()
            for name, digest in self.tool_digests.items()
        ):
            raise ValueError("tool_digests must contain non-empty names and digests.")

    def fingerprint_payload(self) -> dict[str, Any]:
        """Return the behaviorally relevant state fields."""
        return {
            "agent_version": self.agent_version,
            "model": self.model,
            "prompt_digest": self.prompt_digest,
            "tool_digests": dict(sorted(self.tool_digests.items())),
            "retrieval_digest": self.retrieval_digest,
            "memory_digest": self.memory_digest,
            "policy_digest": self.policy_digest,
        }

    def fingerprint(self) -> str:
        """Return SHA-256 of state-defining fields, excluding capture metadata."""
        return sha256(_canonical_json(self.fingerprint_payload())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-compatible state representation."""
        return {
            "state_id": self.state_id,
            "captured_at": self.captured_at.astimezone(UTC).isoformat(),
            **self.fingerprint_payload(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JsonValue]) -> "SystemState":
        """Construct a state snapshot from a JSON-compatible mapping."""
        required = (
            "state_id",
            "captured_at",
            "agent_version",
            "model",
            "prompt_digest",
        )
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValueError(f"Missing required state fields: {', '.join(missing)}")
        tools = payload.get("tool_digests", {})
        if not isinstance(tools, dict):
            raise ValueError("tool_digests must be a JSON object.")
        return cls(
            state_id=str(payload["state_id"]),
            captured_at=parse_datetime(
                str(payload["captured_at"]), field="captured_at"
            ),
            agent_version=str(payload["agent_version"]),
            model=str(payload["model"]),
            prompt_digest=str(payload["prompt_digest"]),
            tool_digests={str(k): str(v) for k, v in tools.items()},
            retrieval_digest=(
                None
                if payload.get("retrieval_digest") is None
                else str(payload["retrieval_digest"])
            ),
            memory_digest=(
                None
                if payload.get("memory_digest") is None
                else str(payload["memory_digest"])
            ),
            policy_digest=(
                None
                if payload.get("policy_digest") is None
                else str(payload["policy_digest"])
            ),
        )
