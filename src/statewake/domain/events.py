"""Framework-neutral event envelope for recorded agent runs."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from statewake.utils.json_support import JsonValue, string_mapping
from statewake.utils.time import parse_datetime


def _empty_string_mapping() -> dict[str, str]:
    """Create an empty string-to-string metadata mapping."""
    return {}


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    """Immutable, JSON-serializable description of one run event."""

    run_id: str
    sequence: int
    occurred_at: datetime
    event_type: str
    actor: str
    name: str | None = None
    state_id: str | None = None
    payload_ref: str | None = None
    metadata: dict[str, str] = field(default_factory=_empty_string_mapping)

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if not self.run_id.strip():
            raise ValueError("run_id must not be empty.")
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative.")
        if not self.event_type.strip():
            raise ValueError("event_type must not be empty.")
        if not self.actor.strip():
            raise ValueError("actor must not be empty.")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware.")

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-compatible representation."""
        return {
            "run_id": self.run_id,
            "sequence": self.sequence,
            "occurred_at": self.occurred_at.astimezone(UTC).isoformat(),
            "event_type": self.event_type,
            "actor": self.actor,
            "name": self.name,
            "state_id": self.state_id,
            "payload_ref": self.payload_ref,
            "metadata": dict(sorted(self.metadata.items())),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, JsonValue]) -> "EventEnvelope":
        """Construct an event from its JSON-compatible representation."""
        required = ("run_id", "sequence", "occurred_at", "event_type", "actor")
        missing = [key for key in required if key not in payload]
        if missing:
            raise ValueError(f"Missing required event fields: {', '.join(missing)}")

        sequence = payload["sequence"]
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            raise ValueError("sequence must be a JSON integer.")
        occurred_at = parse_datetime(str(payload["occurred_at"]), field="occurred_at")
        metadata = string_mapping(payload.get("metadata", {}))

        return cls(
            run_id=str(payload["run_id"]),
            sequence=sequence,
            occurred_at=occurred_at,
            event_type=str(payload["event_type"]),
            actor=str(payload["actor"]),
            name=None if payload.get("name") is None else str(payload["name"]),
            state_id=None
            if payload.get("state_id") is None
            else str(payload["state_id"]),
            payload_ref=None
            if payload.get("payload_ref") is None
            else str(payload["payload_ref"]),
            metadata=metadata,
        )
