"""Durable, hash-linked storage for security-incident evidence records."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from filelock import FileLock, Timeout

from statewake.domain.security_incident import SecurityIncidentEvidence


@dataclass(frozen=True, slots=True)
class StoredIncidentRecord:
    """One incident record linked to the previous stored incident."""

    sequence: int
    recorded_at: datetime
    incident: SecurityIncidentEvidence
    previous_digest: str | None
    digest: str

    def unsigned_payload(self) -> dict[str, object]:
        """Return the canonical storage payload excluding the storage digest."""
        return {
            "sequence": self.sequence,
            "recorded_at": self.recorded_at.astimezone(UTC).isoformat(),
            "incident": self.incident.to_dict(),
            "previous_digest": self.previous_digest,
        }

    def to_dict(self) -> dict[str, object]:
        """Return the canonical stored record."""
        payload = self.unsigned_payload()
        payload["digest"] = self.digest
        return payload

    def verify(self, *, expected_previous: str | None) -> None:
        """Verify sequence, incident digest, and storage-chain continuity."""
        if self.previous_digest != expected_previous:
            raise ValueError("incident evidence storage chain is discontinuous")
        if self.incident.incident_digest != self.incident.digest():
            raise ValueError("security incident evidence digest mismatch")
        canonical = json.dumps(
            self.unsigned_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        expected = sha256(canonical).hexdigest()
        if self.digest != expected:
            raise ValueError("incident evidence storage digest mismatch")


class JsonlIncidentEvidenceStore:
    """Persist incident records as an independently hash-linked JSONL chain."""

    def __init__(self, path: Path, *, lock_timeout_seconds: float = 5.0) -> None:
        """Initialize a host-managed incident-evidence store."""
        self.path = path
        self.lock_path = path.with_name(f".{path.name}.lock")
        self.lock_timeout_seconds = lock_timeout_seconds

    def append(self, incident: SecurityIncidentEvidence) -> StoredIncidentRecord:
        """Append an incident record after validating its internal forensic contract."""
        incident.verify_forensic_continuity() if incident.status == "reverified" else None
        with self._lock():
            records = self._read_unlocked()
            previous = records[-1] if records else None
            record = StoredIncidentRecord(
                sequence=len(records),
                recorded_at=datetime.now(UTC),
                incident=incident,
                previous_digest=None if previous is None else previous.digest,
                digest="",
            )
            canonical = json.dumps(
                record.unsigned_payload(), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
            record = StoredIncidentRecord(
                sequence=record.sequence,
                recorded_at=record.recorded_at,
                incident=record.incident,
                previous_digest=record.previous_digest,
                digest=sha256(canonical).hexdigest(),
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
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

    def read(self) -> list[StoredIncidentRecord]:
        """Read and verify the complete incident-evidence chain."""
        with self._lock():
            return self._read_unlocked()

    def _read_unlocked(self) -> list[StoredIncidentRecord]:
        """Read and verify records while holding the store lock."""
        if not self.path.exists():
            return []
        records: list[StoredIncidentRecord] = []
        with self.path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    if not isinstance(payload, dict):
                        raise ValueError("incident evidence record must be an object")
                    incident_payload = payload["incident"]
                    if not isinstance(incident_payload, dict):
                        raise ValueError("incident must be an object")
                    incident_digest = str(incident_payload.get("incident_digest", ""))
                    if not incident_digest:
                        raise ValueError("incident_digest is required")
                    format_version = incident_payload.get("format_version", "1")
                    if str(format_version) != "1":
                        raise ValueError("unsupported incident evidence format version")
                    incident = _incident_from_dict(incident_payload)
                    recorded_at = datetime.fromisoformat(str(payload["recorded_at"]))
                    if recorded_at.tzinfo is None:
                        raise ValueError("recorded_at must be timezone-aware")
                    previous = payload.get("previous_digest")
                    digest = str(payload["digest"])
                    record = StoredIncidentRecord(
                        sequence=_require_int(payload, "sequence"),
                        recorded_at=recorded_at,
                        incident=incident,
                        previous_digest=None if previous is None else str(previous),
                        digest=digest,
                    )
                    record.verify(
                        expected_previous=records[-1].digest if records else None
                    )
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"invalid incident evidence record at line {line_number}: {exc}"
                    ) from exc
                if record.sequence != len(records):
                    raise ValueError("incident evidence sequence is not contiguous")
                records.append(record)
        return records

    class _Lock:
        """Represent the process-shared lock for the incident store."""

        def __init__(self, owner: JsonlIncidentEvidenceStore) -> None:
            """Bind a file lock to the owning store."""
            self.owner = owner
            self.lock = FileLock(str(owner.lock_path))

        def __enter__(self) -> JsonlIncidentEvidenceStore._Lock:
            """Acquire the store lock."""
            try:
                self.lock.acquire(timeout=self.owner.lock_timeout_seconds)
            except Timeout as exc:
                raise TimeoutError(
                    f"timed out acquiring incident evidence lock: {self.owner.lock_path}"
                ) from exc
            return self

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            tb: object | None,
        ) -> None:
            """Release the store lock."""
            self.lock.release()

    def _lock(self) -> JsonlIncidentEvidenceStore._Lock:
        """Return the process-shared lock context."""
        return self._Lock(self)


def _require_int(payload: dict[str, object], field: str) -> int:
    """Validate a non-negative integer field."""
    value = payload.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a non-negative integer")
    return value


def _incident_from_dict(payload: dict[str, object]) -> SecurityIncidentEvidence:
    """Reconstruct an incident record from canonical storage JSON."""
    from datetime import datetime

    def evidence(value: object) -> IncidentEvidenceReference:
        """Normalize one serialized incident evidence reference."""
        if not isinstance(value, dict):
            raise ValueError("evidence reference must be an object")
        return IncidentEvidenceReference(
            kind=str(value["kind"]),
            identity=str(value["identity"]),
            digest=str(value["digest"]),
            source=None if value.get("source") is None else str(value["source"]),
        )

    def items(value: object) -> list[object]:
        """Require an array before iterating serialized evidence records."""
        if not isinstance(value, list):
            raise ValueError("incident collection must be an array")
        return value

    from statewake.domain.security_incident import (
        AffectedTrustState,
        IncidentEvidenceReference,
        KeyCompromiseImpact,
        PostRecoveryVerification,
        RecoveryEvidence,
    )

    affected_states = []
    for item in items(payload.get("affected_states", [])):
        if not isinstance(item, dict):
            raise ValueError("affected state must be an object")
        affected_states.append(
            AffectedTrustState(
                state_id=str(item["state_id"]),
                state_digest=str(item["state_digest"]),
                trust_context=str(item["trust_context"]),
                affected_window_start=None
                if item.get("affected_window_start") is None
                else datetime.fromisoformat(str(item["affected_window_start"])),
                affected_window_end=None
                if item.get("affected_window_end") is None
                else datetime.fromisoformat(str(item["affected_window_end"])),
            )
        )

    key_payload = payload.get("key_compromise")
    key_compromise = None
    if isinstance(key_payload, dict):
        key_compromise = KeyCompromiseImpact(
            key_identity=str(key_payload["key_identity"]),
            affected_key_version=str(key_payload["affected_key_version"]),
            affected_attestation_ids=tuple(
                str(value)
                for value in items(key_payload.get("affected_attestation_ids", []))
            ),
            affected_evidence=tuple(
                evidence(value)
                for value in items(key_payload.get("affected_evidence", []))
            ),
            exposure_start=datetime.fromisoformat(str(key_payload["exposure_start"])),
            exposure_end=None
            if key_payload.get("exposure_end") is None
            else datetime.fromisoformat(str(key_payload["exposure_end"])),
        )

    recovery_payload = payload.get("recovery")
    recovery = None
    if isinstance(recovery_payload, dict):
        recovery_evidence = recovery_payload["evidence_ref"]
        if not isinstance(recovery_evidence, dict):
            raise ValueError("recovery evidence_ref must be an object")
        recovery = RecoveryEvidence(
            recovery_id=str(recovery_payload["recovery_id"]),
            evidence_ref=evidence(recovery_evidence),
            actor=str(recovery_payload["actor"]),
            source_incident_id=str(recovery_payload["source_incident_id"]),
            status=cast(Any, str(recovery_payload["status"])),
        )

    post_payload = payload.get("post_recovery")
    post_recovery = None
    if isinstance(post_payload, dict):
        post_recovery = PostRecoveryVerification(
            verification_id=str(post_payload["verification_id"]),
            evidence_refs=tuple(
                evidence(value)
                for value in items(post_payload.get("evidence_refs", []))
            ),
            actor=str(post_payload["actor"]),
            status=cast(Any, str(post_payload["status"])),
            performed_at=datetime.fromisoformat(str(post_payload["performed_at"])),
        )

    return SecurityIncidentEvidence(
        incident_id=str(payload["incident_id"]),
        event_id=str(payload["event_id"]),
        detected_at=datetime.fromisoformat(str(payload["detected_at"])),
        actor=str(payload["actor"]),
        category=str(payload["category"]),
        status=cast(Any, str(payload["status"])),
        evidence_refs=tuple(
            evidence(value) for value in items(payload.get("evidence_refs", []))
        ),
        affected_states=tuple(affected_states),
        security_event_digests=tuple(
            str(value) for value in items(payload.get("security_event_digests", []))
        ),
        uncertainty=tuple(
            str(value) for value in items(payload.get("uncertainty", []))
        ),
        key_compromise=key_compromise,
        recovery=recovery,
        post_recovery=post_recovery,
        incident_digest=str(payload["incident_digest"]),
    )
