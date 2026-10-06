"""Durable adapters for generic reliability outcome attestations."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from filelock import FileLock, Timeout

from ..domain.reliability_attestation import (
    ReliabilityOutcomeAttestation,
    SignedReliabilityOutcomeEnvelope,
)
from ..domain.reliability_attestation_trust_context import (
    ReliabilityAttestationTrustContext,
)

_SIGNED_BINDING_RECORD_TYPE = "signed-reliability-outcome-binding.v1"


def _canonical(payload: dict[str, Any]) -> bytes:
    """Return deterministic UTF-8 JSON bytes for persisted binding identity."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class SignedReliabilityOutcomeBinding:
    """Persisted binding between a signed attestation and its exact trust context."""

    envelope: SignedReliabilityOutcomeEnvelope
    trust_context: ReliabilityAttestationTrustContext

    def __post_init__(self) -> None:
        """Validate all structural cross-bindings without re-verifying signatures."""
        attestation = ReliabilityOutcomeAttestation.from_dict(self.envelope.attestation)
        context = self.trust_context
        if attestation.signing_key_id is None:
            raise ValueError(
                "signed reliability attestation must record signing_key_id"
            )
        if self.envelope.key_id != attestation.signing_key_id:
            raise ValueError(
                "signed reliability envelope key does not match attestation signing_key_id"
            )
        if context.attestation_id != attestation.attestation_id:
            raise ValueError("signed reliability trust context attestation_id mismatch")
        if context.attestation_digest != attestation.digest:
            raise ValueError(
                "signed reliability trust context attestation digest mismatch"
            )
        if context.signing_key_id != self.envelope.key_id:
            raise ValueError("signed reliability trust context signing key mismatch")
        envelope_digest = sha256(_canonical(self.envelope.to_dict())).hexdigest()
        if context.envelope_digest != envelope_digest:
            raise ValueError(
                "signed reliability trust context envelope digest mismatch"
            )

    @property
    def attestation(self) -> ReliabilityOutcomeAttestation:
        """Return the canonical attestation embedded in the signed envelope."""
        return ReliabilityOutcomeAttestation.from_dict(self.envelope.attestation)

    def to_record_dict(self) -> dict[str, Any]:
        """Serialize the binding as one canonical sidecar record in the JSONL store."""
        return {
            "record_type": _SIGNED_BINDING_RECORD_TYPE,
            "envelope": self.envelope.to_dict(),
            "trust_context": self.trust_context.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class ReliabilityAttestationSnapshot:
    """Verified bounded snapshot of one canonical attestation JSONL chain."""

    records: tuple[ReliabilityOutcomeAttestation, ...]
    byte_size: int
    exists: bool
    signed_bindings: tuple[SignedReliabilityOutcomeBinding, ...] = ()

    def binding_for(
        self, attestation_id: str
    ) -> SignedReliabilityOutcomeBinding | None:
        """Return the unique recorded signed binding for an attestation, if present."""
        for binding in self.signed_bindings:
            if binding.attestation.attestation_id == attestation_id:
                return binding
        return None


def _parse_attestation_snapshot_lines(
    lines: Iterable[str], *, max_records: int | None = None
) -> tuple[list[ReliabilityOutcomeAttestation], list[SignedReliabilityOutcomeBinding]]:
    """Parse one mixed legacy/signed canonical reliability-attestation store."""
    if max_records is not None and max_records <= 0:
        raise ValueError("max_records must be positive when provided")
    records: list[ReliabilityOutcomeAttestation] = []
    bindings: list[SignedReliabilityOutcomeBinding] = []
    by_id: dict[str, ReliabilityOutcomeAttestation] = {}
    bound_ids: set[str] = set()
    previous = ""
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError("attestation record must be a JSON object")
            if payload.get("record_type") == _SIGNED_BINDING_RECORD_TYPE:
                if set(payload) != {"record_type", "envelope", "trust_context"}:
                    raise ValueError(
                        "signed attestation binding has unsupported fields"
                    )
                envelope_payload = payload.get("envelope")
                context_payload = payload.get("trust_context")
                if not isinstance(envelope_payload, dict) or not isinstance(
                    context_payload, dict
                ):
                    raise ValueError(
                        "signed attestation binding envelope and trust context must be objects"
                    )
                binding = SignedReliabilityOutcomeBinding(
                    SignedReliabilityOutcomeEnvelope.from_dict(envelope_payload),  # type: ignore[arg-type]
                    ReliabilityAttestationTrustContext.from_dict(context_payload),  # type: ignore[arg-type]
                )
                attestation = binding.attestation
                recorded = by_id.get(attestation.attestation_id)
                if recorded is None:
                    raise ValueError(
                        "signed attestation binding references an attestation not yet recorded"
                    )
                if recorded != attestation:
                    raise ValueError(
                        "signed attestation binding does not match canonical attestation record"
                    )
                if attestation.attestation_id in bound_ids:
                    raise ValueError("duplicate signed attestation binding record")
                bindings.append(binding)
                bound_ids.add(attestation.attestation_id)
                continue
            if "record_type" in payload:
                raise ValueError("unsupported reliability attestation record type")
            if max_records is not None and len(records) >= max_records:
                raise OverflowError("attestation record count exceeds read limit")
            item = ReliabilityOutcomeAttestation.from_dict(payload)  # type: ignore[arg-type]
            if item.previous_digest != previous:
                raise ValueError("attestation chain continuity mismatch")
            if item.attestation_id in by_id:
                raise ValueError("duplicate reliability outcome attestation identity")
        except (json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
            raise ValueError(
                f"Invalid reliability outcome attestation at line {line_number}: {exc}"
            ) from exc
        records.append(item)
        by_id[item.attestation_id] = item
        previous = item.digest
    return records, bindings


def _parse_attestation_records(
    lines: Iterable[str], *, max_records: int | None = None
) -> list[ReliabilityOutcomeAttestation]:
    """Parse and verify one canonical reliability-attestation chain."""
    records, _ = _parse_attestation_snapshot_lines(lines, max_records=max_records)
    return records


def read_reliability_attestation_snapshot(
    path: Path, *, max_bytes: int, max_records: int
) -> ReliabilityAttestationSnapshot:
    """Read a verified attestation chain without creating locks or mutating it."""
    if max_bytes <= 0 or max_records <= 0:
        raise ValueError("attestation read bounds must be positive")
    path = Path(path)
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError("attestation path cannot traverse a symlink")
    if not path.exists():
        return ReliabilityAttestationSnapshot((), 0, False)
    if not path.is_file():
        raise ValueError("attestation path must be a file")

    # Windows CRT text mode translates CRLF/LF on descriptor I/O.  This reader
    # measures persisted bytes, so request binary mode whenever the platform has it.
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags)
    try:
        opened_size = os.fstat(fd).st_size
        if opened_size > max_bytes:
            raise OverflowError("attestation source exceeds read limit")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(fd, min(65_536, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise OverflowError("attestation source exceeds read limit")
        final_size = os.fstat(fd).st_size
        if final_size != opened_size or total != final_size:
            raise ValueError("attestation source changed during bounded read")
        raw = b"".join(chunks)
    finally:
        os.close(fd)
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("attestation source is not valid UTF-8") from exc
    records, bindings = _parse_attestation_snapshot_lines(
        text.splitlines(), max_records=max_records
    )
    return ReliabilityAttestationSnapshot(tuple(records), total, True, tuple(bindings))


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
        """Append one legacy/unsigned attestation durably under a shared lock."""
        with self._lock():
            records, _ = self._read_snapshot_unlocked()
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
            self._append_bytes(self._attestation_line(attestation))
            return attestation

    def append_signed(
        self,
        binding: SignedReliabilityOutcomeBinding,
    ) -> SignedReliabilityOutcomeBinding:
        """Persist one attestation and its signed trust binding atomically in one append."""
        with self._lock():
            records, bindings = self._read_snapshot_unlocked()
            attestation = binding.attestation
            existing = next(
                (
                    item
                    for item in records
                    if item.attestation_id == attestation.attestation_id
                ),
                None,
            )
            existing_binding = next(
                (
                    item
                    for item in bindings
                    if item.attestation.attestation_id == attestation.attestation_id
                ),
                None,
            )
            if existing is not None and existing != attestation:
                raise ValueError("reliability outcome attestation identity collision.")
            if existing_binding is not None:
                if existing_binding != binding:
                    raise ValueError(
                        "signed reliability attestation binding collision."
                    )
                return existing_binding

            payload = bytearray()
            if existing is None:
                expected = records[-1].digest if records else ""
                if attestation.previous_digest != expected:
                    raise ValueError(
                        "reliability outcome attestation previous_digest does not match the current chain tip."
                    )
                payload.extend(self._attestation_line(attestation))
            payload.extend(self._binding_line(binding))
            self._append_bytes(bytes(payload))
            return binding

    def read(self) -> list[ReliabilityOutcomeAttestation]:
        """Read and validate the complete attestation chain."""
        with self._lock():
            records, _ = self._read_snapshot_unlocked()
            return records

    def read_signed_bindings(self) -> tuple[SignedReliabilityOutcomeBinding, ...]:
        """Read the canonical signed bindings while preserving legacy records."""
        with self._lock():
            _, bindings = self._read_snapshot_unlocked()
            return tuple(bindings)

    def _read_snapshot_unlocked(
        self,
    ) -> tuple[
        list[ReliabilityOutcomeAttestation], list[SignedReliabilityOutcomeBinding]
    ]:
        """Read all attestation and signed-binding records under the store lock."""
        if not self.path.exists():
            return [], []
        with self.path.open(encoding="utf-8") as handle:
            return _parse_attestation_snapshot_lines(handle)

    def _read_unlocked(self) -> list[ReliabilityOutcomeAttestation]:
        """Read and validate attestations while the caller holds the store lock."""
        records, _ = self._read_snapshot_unlocked()
        return records

    @staticmethod
    def _attestation_line(attestation: ReliabilityOutcomeAttestation) -> bytes:
        """Serialize one canonical attestation line."""
        return (
            json.dumps(attestation.to_dict(), sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")

    @staticmethod
    def _binding_line(binding: SignedReliabilityOutcomeBinding) -> bytes:
        """Serialize one canonical signed-binding sidecar line."""
        return (
            json.dumps(binding.to_record_dict(), sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")

    def _append_bytes(self, payload: bytes) -> None:
        """Append and fsync bytes using restrictive create permissions."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Write canonical bytes without Windows CRT newline translation.
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0)
        fd = os.open(self.path, flags, 0o600)
        try:
            offset = 0
            while offset < len(payload):
                offset += os.write(fd, payload[offset:])
            os.fsync(fd)
        finally:
            os.close(fd)

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
