"""Timezone-safe datetime parsing helpers."""

from __future__ import annotations

from datetime import UTC, datetime


def parse_datetime(value: str, *, field: str) -> datetime:
    """Parse an ISO-8601 datetime and require explicit timezone information."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware and include an offset.")
    return parsed.astimezone(UTC)
