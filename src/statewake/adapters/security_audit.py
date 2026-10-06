"""Append-protected security audit storage for higher-assurance deployments."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from filelock import FileLock, Timeout

from .deployment_security import SecurityEvent, SecurityOperation

SecurityAuditEvent = Literal[
    "authentication_failed",
    "authorization_denied",
    "request_rejected",
    "request_admitted",
]


@dataclass(frozen=True, slots=True)
class SecurityAuditRecord:
    """One immutable, hash-linked security event stored outside core state."""

    sequence: int
    occurred_at: datetime
    event: SecurityAuditEvent
    operation: SecurityOperation | None
    method: str
    path: str
    reason: str
    previous_digest: str | None
    digest: str

    def unsigned_payload(self) -> dict[str, object]:
        """Return the canonical payload used to calculate this record's digest."""
        return {
            "sequence": self.sequence,
            "occurred_at": self.occurred_at.astimezone(UTC).isoformat(),
            "event": self.event,
            "operation": self.operation,
            "method": self.method,
            "path": self.path,
            "reason": self.reason,
            "previous_digest": self.previous_digest,
        }

    def to_dict(self) -> dict[str, object]:
        """Return the canonical JSON representation of the record."""
        payload = self.unsigned_payload()
        payload["digest"] = self.digest
        return payload

    def verify(self, *, expected_previous: str | None) -> None:
        """Verify sequence continuity and the record's content digest."""
        if self.previous_digest != expected_previous:
            raise ValueError("security audit chain is discontinuous")
        payload = json.dumps(
            self.unsigned_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        expected_digest = hashlib.sha256(payload).hexdigest()
        if self.digest != expected_digest:
            raise ValueError("security audit record digest mismatch")

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> SecurityAuditRecord:
        """Construct one record from validated JSON-compatible data."""
        occurred_at = datetime.fromisoformat(str(payload["occurred_at"]))
        if occurred_at.tzinfo is None:
            raise ValueError("security audit timestamp must be timezone-aware")
        return cls(
            sequence=_require_int(payload, "sequence"),
            occurred_at=occurred_at,
            event=_require_event(payload["event"]),
            operation=_require_operation(payload.get("operation")),
            method=_require_string(payload, "method"),
            path=_require_string(payload, "path"),
            reason=_require_string(payload, "reason"),
            previous_digest=_optional_digest(payload.get("previous_digest")),
            digest=_require_digest(payload, "digest"),
        )


@dataclass(frozen=True, slots=True)
class SecurityAuditSnapshot:
    """Verified lock-free snapshot of one configured security audit journal."""

    records: tuple[SecurityAuditRecord, ...]
    exists: bool
    byte_size: int


def _parse_security_audit_lines(
    lines: Iterable[str],
    *,
    max_records: int | None = None,
) -> tuple[SecurityAuditRecord, ...]:
    """Parse and verify one complete security-audit chain from text lines."""
    records: list[SecurityAuditRecord] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        if max_records is not None and len(records) >= max_records:
            raise OverflowError("security audit record limit exceeded")
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("security audit record must be an object")
            record = SecurityAuditRecord.from_dict(payload)
            record.verify(expected_previous=records[-1].digest if records else None)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"invalid security audit record at line {line_number}: {exc}"
            ) from exc
        if record.sequence != len(records):
            raise ValueError("security audit sequence is not contiguous")
        records.append(record)
    return tuple(records)


def read_security_audit_snapshot(
    path: Path,
    *,
    max_bytes: int,
    max_records: int,
) -> SecurityAuditSnapshot:
    """Read one verified audit snapshot without taking the writer lock."""
    if max_bytes <= 0 or max_records <= 0:
        raise ValueError("security audit read limits must be positive")
    candidate = path.expanduser()
    if candidate.is_symlink() or any(
        parent.is_symlink() for parent in candidate.parents
    ):
        raise ValueError("security audit path cannot traverse a symlink")
    if not candidate.exists():
        return SecurityAuditSnapshot(records=(), exists=False, byte_size=0)
    # Descriptor I/O must be binary on Windows so persisted CRLF/LF bytes are
    # measured exactly rather than translated by the CRT.
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(candidate, flags)
    try:
        opened_size = os.fstat(fd).st_size
        if opened_size > max_bytes:
            raise OverflowError("security audit byte limit exceeded")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, min(65_536, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise OverflowError("security audit byte limit exceeded")
        final_size = os.fstat(fd).st_size
        if final_size != opened_size or total != final_size:
            raise ValueError("security audit source changed during bounded read")
        raw = b"".join(chunks)
    finally:
        os.close(fd)
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("security audit source is not valid UTF-8") from exc
    records = _parse_security_audit_lines(text.splitlines(), max_records=max_records)
    return SecurityAuditSnapshot(records=records, exists=True, byte_size=total)


class JsonlSecurityAuditStore:
    """Persist deployment security events in an independent append-only file."""

    def __init__(self, path: Path, *, lock_timeout_seconds: float = 5.0) -> None:
        """Initialize the security audit store at an independently managed path."""
        self.path = path
        self.lock_path = path.with_name(f".{path.name}.lock")
        self.lock_timeout_seconds = lock_timeout_seconds

    def append(self, event: SecurityEvent) -> SecurityAuditRecord:
        """Append one security event without storing request payloads or headers."""
        with self._lock():
            records = self._read_unlocked()
            previous = records[-1] if records else None
            record = SecurityAuditRecord(
                sequence=len(records),
                occurred_at=datetime.now(UTC),
                event=event.event,
                operation=event.operation,
                method=event.method,
                path=event.path,
                reason=event.reason,
                previous_digest=previous.digest if previous is not None else None,
                digest="",
            )
            record = _with_digest(record)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0)
            no_follow = getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(self.path, flags | no_follow, 0o600)
            try:
                payload = (
                    json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
                    + "\n"
                ).encode("utf-8")
                offset = 0
                while offset < len(payload):
                    offset += os.write(fd, payload[offset:])
                os.fsync(fd)
            finally:
                os.close(fd)
            return record

    def read(self) -> list[SecurityAuditRecord]:
        """Read and verify the complete audit chain."""
        with self._lock():
            return self._read_unlocked()

    def _lock(self) -> JsonlSecurityAuditStore._Lock:
        """Return the process-shared lock context for this audit store."""
        return self._Lock(self)

    def _read_unlocked(self) -> list[SecurityAuditRecord]:
        """Read and verify records while holding the store lock."""
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as handle:
            return list(_parse_security_audit_lines(handle))

    class _Lock:
        """Represent the process-shared lock for the audit file."""

        def __init__(self, owner: JsonlSecurityAuditStore) -> None:
            """Bind a file lock to the owning audit store."""
            self.owner = owner
            self._lock = FileLock(str(owner.lock_path))

        def __enter__(self) -> JsonlSecurityAuditStore._Lock:
            """Acquire and return the lock context."""
            try:
                self._lock.acquire(timeout=self.owner.lock_timeout_seconds)
            except Timeout as exc:
                raise TimeoutError(
                    f"timed out acquiring security audit lock: {self.owner.lock_path}"
                ) from exc
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: object | None,
        ) -> None:
            """Release the security audit lock."""
            self._lock.release()


def _with_digest(record: SecurityAuditRecord) -> SecurityAuditRecord:
    """Return a copy with the canonical content digest populated."""
    payload = json.dumps(
        record.unsigned_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return SecurityAuditRecord(
        sequence=record.sequence,
        occurred_at=record.occurred_at,
        event=record.event,
        operation=record.operation,
        method=record.method,
        path=record.path,
        reason=record.reason,
        previous_digest=record.previous_digest,
        digest=hashlib.sha256(payload).hexdigest(),
    )


def _require_string(payload: dict[str, object], field: str) -> str:
    """Return one non-empty string field."""
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_int(payload: dict[str, object], field: str) -> int:
    """Return one JSON integer field."""
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _require_digest(payload: dict[str, object], field: str) -> str:
    """Return one SHA-256 hexadecimal digest."""
    value = _require_string(payload, field)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field} must be lowercase SHA-256 hex")
    return value


def _optional_digest(value: object) -> str | None:
    """Validate an optional previous-record digest."""
    if value is None:
        return None
    if not isinstance(value, str) or len(value) != 64:
        raise ValueError("previous_digest must be lowercase SHA-256 hex")
    if any(char not in "0123456789abcdef" for char in value):
        raise ValueError("previous_digest must be lowercase SHA-256 hex")
    return value


def _require_event(value: Any) -> SecurityAuditEvent:
    """Validate the persisted deployment security event type."""
    allowed: tuple[SecurityAuditEvent, ...] = (
        "authentication_failed",
        "authorization_denied",
        "request_rejected",
        "request_admitted",
    )
    if value not in allowed:
        raise ValueError("unsupported security audit event")
    return cast(SecurityAuditEvent, value)


def _require_operation(value: Any) -> SecurityOperation | None:
    """Validate the persisted StateWake operation identifier."""
    if value is None:
        return None
    allowed = (
        "verify:evidence",
        "verify:proof",
        "review:read",
        "review:write",
        "approval:read",
        "approval:write",
    )
    if value not in allowed:
        raise ValueError("unsupported security audit operation")
    return cast(SecurityOperation, value)
