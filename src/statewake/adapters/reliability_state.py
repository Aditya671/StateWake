"""Durable local storage for evidence-backed reliability-state transitions."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Protocol

from filelock import FileLock, Timeout

from ..domain.reliability_state import ReliabilityStateTransition


class ReliabilityStateStore(Protocol):
    """Persistence boundary for authoritative reliability-state history."""

    def append(
        self, transition: ReliabilityStateTransition
    ) -> ReliabilityStateTransition:
        """Append or idempotently return one transition."""
        ...

    def read(self, subject_id: str | None = None) -> list[ReliabilityStateTransition]:
        """Read and verify transition history."""
        ...


class JsonlReliabilityStateStore:
    """Append-only JSONL state history with a small local lock for concurrency."""

    def __init__(
        self,
        path: Path,
        *,
        lock_timeout_seconds: float = 5.0,
        recover_partial_tail: bool = True,
    ) -> None:
        """Initialize this component with its configured state."""
        self.path = path
        self.lock_path = path.with_name(f".{path.name}.lock")
        self.lock_timeout_seconds = lock_timeout_seconds
        self.recover_partial_tail = recover_partial_tail

    def append(
        self, transition: ReliabilityStateTransition
    ) -> ReliabilityStateTransition:
        """Append a reliability-state transition using the store durability contract."""
        with self._lock():
            transitions = self._read_unlocked()
            for existing in transitions:
                if existing.transition_id == transition.transition_id:
                    if existing.to_dict() != transition.to_dict():
                        raise ValueError(
                            f"transition identity collision: {transition.transition_id}"
                        )
                    return existing
            subject_transitions = [
                item for item in transitions if item.subject_id == transition.subject_id
            ]
            previous = subject_transitions[-1] if subject_transitions else None
            expected_previous = previous.computed_digest if previous is not None else ""
            if transition.previous_transition_digest != expected_previous:
                raise ValueError(
                    f"stale reliability-state tip for {transition.subject_id}: "
                    f"expected {expected_previous or '<empty>'}, got {transition.previous_transition_digest or '<empty>'}"
                )
            if previous is not None and transition.from_state != previous.to_state:
                raise ValueError(
                    f"reliability-state predecessor mismatch for {transition.subject_id}: "
                    f"expected from_state {previous.to_state}, got {transition.from_state}"
                )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = (
                json.dumps(transition.to_dict(), sort_keys=True, separators=(",", ":"))
                + "\n"
            ).encode("utf-8")
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                offset = 0
                while offset < len(payload):
                    offset += os.write(fd, payload[offset:])
                os.fsync(fd)
            finally:
                os.close(fd)
            return transition

    def read(self, subject_id: str | None = None) -> list[ReliabilityStateTransition]:
        """Read and validate a consistent snapshot under the state lock."""
        with self._lock():
            return self._read_unlocked(subject_id)

    def _read_unlocked(
        self, subject_id: str | None = None
    ) -> list[ReliabilityStateTransition]:
        """Read and validate state while the caller holds the store lock."""
        if not self.path.exists():
            return []
        if self.recover_partial_tail:
            self._recover_partial_tail()
        result: list[ReliabilityStateTransition] = []
        tips: dict[str, str] = {}
        with self.path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    if not isinstance(payload, dict):
                        raise ValueError("transition record must be a JSON object")
                    transition = ReliabilityStateTransition.from_dict(payload)  # type: ignore
                    expected = tips.get(transition.subject_id, "")
                    if transition.previous_transition_digest != expected:
                        raise ValueError(
                            f"previous transition digest does not match subject tip; expected {expected or '<empty>'}"
                        )
                    if payload.get("digest") != transition.computed_digest:  # type: ignore
                        raise ValueError("stored transition digest mismatch")
                    tips[transition.subject_id] = transition.computed_digest
                except (json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
                    raise ValueError(
                        f"Invalid reliability-state transition at line {line_number}: {exc}"
                    ) from exc
                if subject_id is None or transition.subject_id == subject_id:
                    result.append(transition)
        return result

    def _recover_partial_tail(self) -> None:
        """Truncate an incomplete final UTF-8/JSONL record after a crash."""
        raw = self.path.read_bytes()
        if not raw or raw.endswith(b"\n"):
            return
        last_newline = raw.rfind(b"\n")
        tail = raw[last_newline + 1 :]
        try:
            payload = json.loads(tail.decode("utf-8"))
            if isinstance(payload, dict):
                ReliabilityStateTransition.from_dict(payload)  # type: ignore
                return
        except (
            UnicodeDecodeError,
            json.JSONDecodeError,
            TypeError,
            KeyError,
            ValueError,
        ):
            pass
        if last_newline < 0:
            with self.path.open("r+b") as handle:
                handle.truncate(0)
                handle.flush()
                os.fsync(handle.fileno())
            return
        with self.path.open("r+b") as handle:
            handle.truncate(last_newline + 1)
            handle.flush()
            os.fsync(handle.fileno())

    class _Lock:
        """Represent the file-backed lock for the state store."""

        def __init__(self, owner: JsonlReliabilityStateStore) -> None:
            """Initialize a lock bound to the owning state store."""
            self.owner = owner
            self._lock = FileLock(str(owner.lock_path))

        def __enter__(self) -> JsonlReliabilityStateStore._Lock:
            """Acquire the state-store lock and return this context manager."""
            try:
                self._lock.acquire(timeout=self.owner.lock_timeout_seconds)
            except Timeout as exc:
                raise TimeoutError(
                    f"timed out acquiring reliability-state lock: {self.owner.lock_path}"
                ) from exc
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: object | None,
        ) -> None:
            """Release the state-store lock."""
            self._lock.release()

    def _lock(self) -> JsonlReliabilityStateStore._Lock:
        """Return the lock protecting this reliability-state store."""
        return self._Lock(self)


class SqliteReliabilityStateStore:
    """Transactional SQLite reference adapter for authoritative state history."""

    def __init__(self, path: Path) -> None:
        """Initialize the instance."""
        self.path = path

    def initialize(self) -> None:
        """Create the database and schema if they do not already exist."""
        with closing(self._connect()):
            return

    def _connect(self) -> sqlite3.Connection:
        """Open and return the backing database connection."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=30.0)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("""CREATE TABLE IF NOT EXISTS reliability_state_transitions (
            sequence INTEGER PRIMARY KEY AUTOINCREMENT,
            transition_id TEXT NOT NULL UNIQUE,
            subject_id TEXT NOT NULL,
            digest TEXT NOT NULL,
            payload TEXT NOT NULL
        )""")
        db.commit()
        return db

    def append(
        self, transition: ReliabilityStateTransition
    ) -> ReliabilityStateTransition:
        """Append a reliability state transition durably to the state store."""
        payload = json.dumps(
            transition.to_dict(), sort_keys=True, separators=(",", ":")
        )
        with closing(self._connect()) as db:
            with db:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT payload FROM reliability_state_transitions "
                    "WHERE transition_id=?",
                    (transition.transition_id,),
                ).fetchone()
                if row is not None:
                    existing = ReliabilityStateTransition.from_dict(
                        json.loads(row["payload"])
                    )
                    if existing.to_dict() != transition.to_dict():
                        raise ValueError(
                            f"transition identity collision: {transition.transition_id}"
                        )
                    return existing

                row = db.execute(
                    "SELECT digest, payload FROM reliability_state_transitions "
                    "WHERE subject_id=? ORDER BY sequence DESC LIMIT 1",
                    (transition.subject_id,),
                ).fetchone()
                expected_previous = "" if row is None else str(row["digest"])
                if transition.previous_transition_digest != expected_previous:
                    raise ValueError(
                        f"stale reliability-state tip for {transition.subject_id}: "
                        f"expected {expected_previous or '<empty>'}, "
                        f"got {transition.previous_transition_digest or '<empty>'}"
                    )
                if row is not None:
                    previous_payload = json.loads(row["payload"])
                    previous = ReliabilityStateTransition.from_dict(previous_payload)
                    if transition.from_state != previous.to_state:
                        raise ValueError(
                            f"reliability-state predecessor mismatch for "
                            f"{transition.subject_id}: expected from_state "
                            f"{previous.to_state}, got {transition.from_state}"
                        )
                try:
                    db.execute(
                        "INSERT INTO reliability_state_transitions "
                        "(transition_id,subject_id,digest,payload) VALUES (?,?,?,?)",
                        (
                            transition.transition_id,
                            transition.subject_id,
                            transition.computed_digest,
                            payload,
                        ),
                    )
                except sqlite3.IntegrityError:
                    raise
        return transition

    def read(self, subject_id: str | None = None) -> list[ReliabilityStateTransition]:
        """Read transitions and verify stored digest-chain continuity."""
        with closing(self._connect()) as db:
            if subject_id is None:
                rows = db.execute(
                    "SELECT sequence, subject_id, digest, payload FROM reliability_state_transitions ORDER BY sequence"
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT sequence, subject_id, digest, payload FROM reliability_state_transitions "
                    "WHERE subject_id=? ORDER BY sequence",
                    (subject_id,),
                ).fetchall()
        result: list[ReliabilityStateTransition] = []
        tips: dict[str, str] = {}
        for row in rows:
            try:
                payload = json.loads(row["payload"])
                if not isinstance(payload, dict):
                    raise ValueError("transition record must be a JSON object")
                transition = ReliabilityStateTransition.from_dict(payload)  # type: ignore
                if row["subject_id"] != transition.subject_id:
                    raise ValueError(
                        "stored transition subject_id column does not match payload"
                    )
                if row["digest"] != transition.computed_digest:
                    raise ValueError(
                        "stored transition digest column does not match payload"
                    )
                expected = tips.get(transition.subject_id, "")
                if transition.previous_transition_digest != expected:
                    raise ValueError(
                        "previous transition digest does not match subject tip; "
                        f"expected {expected or '<empty>'}"
                    )
                if payload.get("digest") != transition.computed_digest:  # type: ignore
                    raise ValueError("stored transition digest mismatch")
                tips[transition.subject_id] = transition.computed_digest
            except (json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
                sequence = row["sequence"]
                raise ValueError(
                    f"Invalid reliability-state transition at SQLite sequence {sequence}: {exc}"
                ) from exc
            result.append(transition)
        return result
