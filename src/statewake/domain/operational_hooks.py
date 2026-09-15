"""Small host-facing hooks for important StateWake failures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ReliabilityFailureEvent:
    """Event emitted when verification or authoritative persistence fails."""

    event_type: str
    operation: str
    subject_id: str | None
    message: str
    occurred_at: str

    @classmethod
    def now(
        cls,
        event_type: str,
        operation: str,
        message: str,
        *,
        subject_id: str | None = None,
    ) -> ReliabilityFailureEvent:
        """Return the current UTC timestamp."""
        return cls(
            event_type, operation, subject_id, message, datetime.now(UTC).isoformat()
        )

    def to_dict(self) -> dict[str, str | None]:
        """Serialize this object to a dictionary."""
        return {
            "event_type": self.event_type,
            "operation": self.operation,
            "subject_id": self.subject_id,
            "message": self.message,
            "occurred_at": self.occurred_at,
        }


class ReliabilityFailureHook(Protocol):
    """Minimal callback boundary for hosts that need operational notification."""

    def emit(self, event: ReliabilityFailureEvent) -> None:
        """Receive one already-classified failure event."""
        ...


class NullReliabilityFailureHook:
    """Default no-op hook so reliability processing has no observability dependency."""

    def emit(self, event: ReliabilityFailureEvent) -> None:
        """Emit the operational hook event through the configured sink."""
        return None
