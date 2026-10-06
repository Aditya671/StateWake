"""Append-only durable history for signed attestation trust-state snapshots."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from filelock import FileLock, Timeout

from statewake.domain.attestation_trust import (
    AttestationTrustStateVerifier,
    SignedAttestationTrustState,
    validate_attestation_trust_transition,
)


@dataclass(frozen=True, slots=True)
class AttestationTrustHistorySnapshot:
    """Bounded structurally verified trust-state history snapshot."""

    records: tuple[SignedAttestationTrustState, ...]
    byte_size: int
    exists: bool


def _parse_history_records(
    lines: Iterable[str], *, max_records: int | None = None
) -> list[SignedAttestationTrustState]:
    """Parse and verify one append-only trust-state history chain."""
    if max_records is not None and max_records <= 0:
        raise ValueError("max_records must be positive when provided")
    result: list[SignedAttestationTrustState] = []
    previous: SignedAttestationTrustState | None = None
    previously_seen: set[str] = set()
    previous_ids: set[str] = set()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        if max_records is not None and len(result) >= max_records:
            raise OverflowError(
                "attestation trust history record count exceeds read limit"
            )
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(
                    "attestation trust history record must be a JSON object"
                )
            state = SignedAttestationTrustState.from_dict(payload)  # type: ignore[arg-type]
            validate_attestation_trust_transition(previous, state)
            current_ids = {anchor.key_id for anchor in state.anchors}
            if previous is not None:
                reappeared = (current_ids & previously_seen) - previous_ids
                if reappeared:
                    raise ValueError(
                        "attestation trust key cannot reappear after removal: "
                        + ", ".join(sorted(reappeared))
                    )
            previously_seen.update(current_ids)
            previous_ids = current_ids
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError(
                f"Invalid attestation trust history at line {line_number}: {exc}"
            ) from exc
        result.append(state)
        previous = state
    return result


def read_attestation_trust_history_snapshot(
    path: Path, *, max_bytes: int, max_records: int
) -> AttestationTrustHistorySnapshot:
    """Read a bounded trust-state history without mutating it or creating locks."""
    if max_bytes <= 0 or max_records <= 0:
        raise ValueError("attestation trust history read bounds must be positive")
    path = Path(path)
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError("attestation trust history path cannot traverse a symlink")
    if not path.exists():
        return AttestationTrustHistorySnapshot((), 0, False)
    if not path.is_file():
        raise ValueError("attestation trust history path must be a file")

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, min(65_536, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise OverflowError("attestation trust history exceeds read limit")
        raw = b"".join(chunks)
    finally:
        os.close(fd)
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("attestation trust history is not valid UTF-8") from exc
    records = _parse_history_records(text.splitlines(), max_records=max_records)
    return AttestationTrustHistorySnapshot(tuple(records), len(raw), True)


class JsonlAttestationTrustHistoryStore:
    """Append authenticated signed trust states to one hash-linked history."""

    def __init__(
        self,
        path: Path,
        verifier: AttestationTrustStateVerifier,
        *,
        lock_timeout_seconds: float = 5.0,
    ) -> None:
        """Configure the durable history path, verifier, and lock timeout."""
        self.path = Path(path)
        self.verifier = verifier
        self.lock_path = self.path.with_name(f".{self.path.name}.lock")
        self.lock_timeout_seconds = lock_timeout_seconds

    def append(self, state: SignedAttestationTrustState) -> SignedAttestationTrustState:
        """Authenticate and append one state, preserving idempotent exact replay."""
        if self.path.is_symlink() or any(
            parent.is_symlink() for parent in self.path.parents
        ):
            raise ValueError("attestation trust history path cannot traverse a symlink")
        if self.lock_path.is_symlink():
            raise ValueError("attestation trust history lock path cannot be a symlink")
        verified = self.verifier.verify(state)
        with self._lock():
            records = self._read_unlocked()
            for existing in records:
                if existing.version == verified.version:
                    if existing.to_dict() == verified.to_dict():
                        return existing
                    raise ValueError(
                        "attestation trust history version already exists with different contents"
                    )
            previous = records[-1] if records else None
            validate_attestation_trust_transition(previous, verified)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(self.path, flags, 0o600)
            try:
                payload = (
                    json.dumps(
                        verified.to_dict(), sort_keys=True, separators=(",", ":")
                    )
                    + "\n"
                ).encode("utf-8")
                view = memoryview(payload)
                while view:
                    written = os.write(fd, view)
                    if written <= 0:
                        raise OSError("failed to append attestation trust history")
                    view = view[written:]
                os.fsync(fd)
                # sys.platform lets static checkers narrow this POSIX-only API.
                if sys.platform != "win32":
                    os.fchmod(fd, 0o600)
            finally:
                os.close(fd)
        return verified

    def read(self) -> tuple[SignedAttestationTrustState, ...]:
        """Read and authenticate the complete local history."""
        with self._lock():
            return tuple(self._read_unlocked())

    def _read_unlocked(self) -> list[SignedAttestationTrustState]:
        if not self.path.exists():
            return []
        snapshot = read_attestation_trust_history_snapshot(
            self.path,
            max_bytes=max(self.path.stat().st_size + 1, 1),
            max_records=1_000_000,
        )
        records = list(snapshot.records)
        for state in records:
            self.verifier.verify(state)
        return records

    def _lock(self) -> JsonlAttestationTrustHistoryStore._Lock:
        """Return the process-shared lock context for this history store."""
        return self._Lock(self)

    class _Lock:
        """Represent the file-backed lock for the trust-history store."""

        def __init__(self, owner: JsonlAttestationTrustHistoryStore) -> None:
            self.owner = owner
            self._lock = FileLock(str(owner.lock_path))

        def __enter__(self) -> JsonlAttestationTrustHistoryStore._Lock:
            try:
                self._lock.acquire(timeout=self.owner.lock_timeout_seconds)
            except Timeout as exc:
                raise TimeoutError(
                    f"timed out acquiring attestation trust history lock: {self.owner.lock_path}"
                ) from exc
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: object | None,
        ) -> None:
            self._lock.release()
