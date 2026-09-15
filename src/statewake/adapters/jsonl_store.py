"""Local append-only JSONL event storage."""

from __future__ import annotations

import json
import os
from pathlib import Path

from filelock import FileLock, Timeout

from ..domain.events import EventEnvelope


class JsonlEventStore:
    """Persist event envelopes as one canonical JSON object per line."""

    def __init__(self, path: Path, *, lock_timeout_seconds: float = 5.0) -> None:
        """Initialize this component with its configured state."""
        self.path = path
        self.lock_path = path.with_name(f".{path.name}.lock")
        self.lock_timeout_seconds = lock_timeout_seconds

    def append(self, event: EventEnvelope) -> None:
        """Append one event durably under the store's process-shared lock."""
        payload = (
            json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")  # ruff: ignore[line-too-long]
        with self._lock():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                offset = 0
                while offset < len(payload):
                    offset += os.write(fd, payload[offset:])
                os.fsync(fd)
            finally:
                os.close(fd)

    def read(self, run_id: str | None = None) -> list[EventEnvelope]:
        """Read events and optionally filter them by run id."""
        with self._lock():
            return self._read_unlocked(run_id)

    def _read_unlocked(self, run_id: str | None = None) -> list[EventEnvelope]:
        """Read events while the caller holds the process-shared lock."""
        if not self.path.exists():
            return []

        events: list[EventEnvelope] = []
        with self.path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    if not isinstance(payload, dict):
                        raise ValueError("event record must be a JSON object")
                    event = EventEnvelope.from_dict(payload)  # type: ignore
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    raise ValueError(
                        f"Invalid event at line {line_number}: {exc}"
                    ) from exc
                if run_id is None or event.run_id == run_id:
                    events.append(event)

        return events

    def validate_run(self, run_id: str) -> list[EventEnvelope]:
        """Validate that a stored run has a contiguous, single-run sequence."""
        events = self.read(run_id)
        for expected_sequence, event in enumerate(events):
            if event.sequence != expected_sequence:
                raise ValueError(
                    f"Run {run_id!r} has sequence {event.sequence}; "
                    f"expected {expected_sequence}."
                )
        return events

    def _lock(self) -> JsonlEventStore._Lock:
        """Return the process-shared lock context for this event store."""
        return self._Lock(self)

    class _Lock:
        """Represent the file-backed lock for the event store."""

        def __init__(self, owner: JsonlEventStore) -> None:
            """Initialize a lock bound to the owning event store."""
            self.owner = owner
            self._lock = FileLock(str(owner.lock_path))

        def __enter__(self) -> JsonlEventStore._Lock:
            """Acquire and return this lock context."""
            try:
                self._lock.acquire(timeout=self.owner.lock_timeout_seconds)
            except Timeout as exc:
                raise TimeoutError(
                    f"timed out acquiring event-store lock: {self.owner.lock_path}"
                ) from exc
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: object | None,
        ) -> None:
            """Release the event-store lock."""
            self._lock.release()
