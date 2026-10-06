"""Append-only local persistence for human review statements."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from filelock import FileLock, Timeout

from statewake.domain.review_statement import (
    ReviewCategory,
    ReviewStatementRecord,
    review_request_fingerprint,
    with_review_digest,
)


class IdempotencyConflictError(ValueError):
    """Raised when one idempotency key is reused for a different review request."""


class ReviewSupersessionError(ValueError):
    """Raised when a correction attempts to supersede an incompatible record."""


class JsonlReviewStatementStore:
    """Persist immutable review statements in a hash-linked append-only JSONL file."""

    def __init__(
        self,
        path: Path,
        *,
        lock_timeout_seconds: float = 5.0,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize one independently managed review-statement store."""
        self.path = path.expanduser().resolve()
        self.lock_path = self.path.with_name(f".{self.path.name}.lock")
        self.lock_timeout_seconds = lock_timeout_seconds
        self._now = now or (lambda: datetime.now(UTC))

    def append(
        self,
        *,
        target_record_id: str,
        candidate_identity: str,
        candidate_digest: str,
        report_digest: str,
        profile_id: str,
        profile_version: str,
        actor_identity_ref: str,
        actor_role: str,
        category: ReviewCategory,
        statement: str,
        finding_refs: tuple[str, ...],
        limitation: str | None,
        scope: str,
        idempotency_key: str,
        supersedes_digest: str | None = None,
    ) -> tuple[ReviewStatementRecord, bool]:
        """Append one review statement or return its exact idempotent predecessor."""
        fingerprint = review_request_fingerprint(
            target_record_id=target_record_id,
            candidate_identity=candidate_identity,
            candidate_digest=candidate_digest,
            report_digest=report_digest,
            profile_id=profile_id,
            profile_version=profile_version,
            actor_identity_ref=actor_identity_ref,
            actor_role=actor_role,
            category=category,
            statement=statement,
            finding_refs=finding_refs,
            limitation=limitation,
            scope=scope,
            supersedes_digest=supersedes_digest,
        )
        with self._lock():
            records = self._read_unlocked()
            for existing in records:
                if existing.idempotency_key != idempotency_key:
                    continue
                if existing.request_fingerprint != fingerprint:
                    raise IdempotencyConflictError(
                        "idempotency key was already used for a different review request"
                    )
                return existing, False

            if supersedes_digest is not None:
                superseded = next(
                    (item for item in records if item.digest == supersedes_digest), None
                )
                if superseded is None:
                    raise ReviewSupersessionError(
                        "superseded review statement does not exist"
                    )
                if (
                    superseded.target_record_id != target_record_id
                    or superseded.report_digest != report_digest
                    or superseded.actor_identity_ref != actor_identity_ref
                ):
                    raise ReviewSupersessionError(
                        "review correction cannot supersede a different target or author"
                    )

            previous = records[-1] if records else None
            created_at = self._now()
            if created_at.tzinfo is None:
                raise ValueError(
                    "review statement clock must return timezone-aware time"
                )
            record = ReviewStatementRecord(
                sequence=len(records),
                target_record_id=target_record_id,
                candidate_identity=candidate_identity,
                candidate_digest=candidate_digest,
                report_digest=report_digest,
                profile_id=profile_id,
                profile_version=profile_version,
                actor_identity_ref=actor_identity_ref,
                actor_role=actor_role,
                category=category,
                statement=statement,
                finding_refs=finding_refs,
                limitation=limitation,
                scope=scope,
                created_at=created_at,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
                supersedes_digest=supersedes_digest,
                previous_digest=previous.digest if previous is not None else None,
                digest="0" * 64,
            )
            record = with_review_digest(record)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
            flags |= getattr(os, "O_NOFOLLOW", 0)
            fd = os.open(self.path, flags, 0o600)
            try:
                raw = (
                    json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":"))
                    + "\n"
                ).encode("utf-8")
                offset = 0
                while offset < len(raw):
                    offset += os.write(fd, raw[offset:])
                os.fsync(fd)
            finally:
                os.close(fd)
            return record, True

    def read(self) -> list[ReviewStatementRecord]:
        """Read and cryptographically verify the complete append-only history."""
        with self._lock():
            return self._read_unlocked()

    def for_target(
        self, target_record_id: str, *, report_digest: str
    ) -> list[ReviewStatementRecord]:
        """Return exact-basis review statements for one immutable report target."""
        return [
            record
            for record in self.read()
            if record.target_record_id == target_record_id
            and record.report_digest == report_digest
        ]

    def _read_unlocked(self) -> list[ReviewStatementRecord]:
        """Read and verify records while the process-shared lock is held."""
        if not self.path.exists():
            return []
        records: list[ReviewStatementRecord] = []
        with self.path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    if not isinstance(payload, dict):
                        raise ValueError("review statement record must be an object")
                    record = ReviewStatementRecord.from_dict(payload)
                    record.verify(
                        expected_sequence=len(records),
                        expected_previous=records[-1].digest if records else None,
                    )
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise ValueError(
                        f"invalid review statement at line {line_number}: {exc}"
                    ) from exc
                records.append(record)
        return records

    class _Lock:
        """Wrap the cross-process file lock used by one review store."""

        def __init__(self, owner: JsonlReviewStatementStore) -> None:
            """Bind the lock context to its owning store."""
            self.owner = owner
            self._lock = FileLock(str(owner.lock_path))

        def __enter__(self) -> JsonlReviewStatementStore._Lock:
            """Acquire the lock or fail rather than racing an append."""
            try:
                self._lock.acquire(timeout=self.owner.lock_timeout_seconds)
            except Timeout as exc:
                raise TimeoutError(
                    f"timed out acquiring review statement lock: {self.owner.lock_path}"
                ) from exc
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            traceback: object | None,
        ) -> None:
            """Release the process-shared review lock."""
            del exc_type, exc, traceback
            self._lock.release()

    def _lock(self) -> JsonlReviewStatementStore._Lock:
        """Return the process-shared append/read lock context."""
        return self._Lock(self)


__all__ = [
    "IdempotencyConflictError",
    "JsonlReviewStatementStore",
    "ReviewSupersessionError",
]
