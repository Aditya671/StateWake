"""Durable adapters for generic reliability outcome attestations."""

from __future__ import annotations

import json
import os
from pathlib import Path

from filelock import FileLock, Timeout

from ..domain.reliability_attestation import ReliabilityOutcomeAttestation


class JsonlReliabilityOutcomeAttestationStore:
    """Append-only, hash-linked local attestation history."""

    def __init__(self, path: Path, *, lock_timeout_seconds: float = 5.0) -> None:
        """Initialize this component with its configured state."""
        self.path = path
        self.lock_path = path.with_name(f".{path.name}.lock")
        self.lock_timeout_seconds = lock_timeout_seconds

    def append(
        self, attestation: ReliabilityOutcomeAttestation
    ) -> ReliabilityOutcomeAttestation:
        """Append one attestation durably under a process-shared lock."""
        with self._lock():
            records = self._read_unlocked()
            for existing in records:
                if existing.attestation_id == attestation.attestation_id:
                    existing_payload = existing.payload().copy()
                    candidate_payload = attestation.payload().copy()
                    existing_payload.pop("previous_digest", None)
                    candidate_payload.pop("previous_digest", None)
                    if existing_payload != candidate_payload:
                        raise ValueError(
                            "reliability outcome attestation identity collision."
                        )
                    return existing
            expected = records[-1].digest if records else ""
            if attestation.previous_digest != expected:
                raise ValueError(
                    "reliability outcome attestation previous_digest does not match the current chain tip."
                )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = (
                json.dumps(attestation.to_dict(), sort_keys=True, separators=(",", ":"))
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
            return attestation

    def read(self) -> list[ReliabilityOutcomeAttestation]:
        """Read and validate the complete attestation chain."""
        with self._lock():
            return self._read_unlocked()

    def _read_unlocked(self) -> list[ReliabilityOutcomeAttestation]:
        """Read and validate attestations while the caller holds the store lock."""
        if not self.path.exists():
            return []
        result: list[ReliabilityOutcomeAttestation] = []
        previous = ""
        with self.path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    if not isinstance(payload, dict):
                        raise ValueError("attestation record must be a JSON object")
                    item = ReliabilityOutcomeAttestation.from_dict(payload)  # type: ignore
                    if item.previous_digest != previous:
                        raise ValueError("attestation chain continuity mismatch")
                    result.append(item)
                    previous = item.digest
                except (json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
                    raise ValueError(
                        f"Invalid reliability outcome attestation at line "
                        f"{line_number}: {exc}"
                    ) from exc
        return result

    def _lock(self) -> JsonlReliabilityOutcomeAttestationStore._Lock:
        """Return the process-shared lock context for this attestation store."""
        return self._Lock(self)

    class _Lock:
        """Represent the file-backed lock for the attestation store."""

        def __init__(self, owner: JsonlReliabilityOutcomeAttestationStore) -> None:
            """Initialize a lock bound to the owning attestation store."""
            self.owner = owner
            self._lock = FileLock(str(owner.lock_path))

        def __enter__(self) -> JsonlReliabilityOutcomeAttestationStore._Lock:
            """Acquire and return this lock context."""
            try:
                self._lock.acquire(timeout=self.owner.lock_timeout_seconds)
            except Timeout as exc:
                raise TimeoutError(
                    f"timed out acquiring attestation-store lock: {self.owner.lock_path}"
                ) from exc
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: object | None,
        ) -> None:
            """Release the attestation-store lock."""
            self._lock.release()
