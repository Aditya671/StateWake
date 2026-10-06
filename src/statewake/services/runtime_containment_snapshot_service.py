"""Persist and strictly reload effective runtime-containment configuration evidence."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from statewake.domain.runtime_containment import RuntimeContainmentLimits

RUNTIME_CONTAINMENT_SNAPSHOT_SCHEMA_VERSION = "runtime-containment-config-snapshot.v1"


def _canonical_json(payload: object) -> bytes:
    """Return deterministic canonical JSON bytes."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _strict_keys(payload: dict[str, Any], *, expected: set[str], name: str) -> None:
    """Require an exact JSON-object shape."""
    actual = set(payload)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{name} fields mismatch; missing={missing}, extra={extra}")


def _int(value: Any, name: str, *, minimum: int = 0) -> int:
    """Return one strict JSON integer."""
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _float(value: Any, name: str, *, minimum: float) -> float:
    """Return one strict finite JSON number."""
    if type(value) not in {int, float}:
        raise ValueError(f"{name} must be numeric")
    number = float(value)
    if not (number >= minimum) or number in {float("inf"), float("-inf")}:
        raise ValueError(f"{name} must be finite and >= {minimum}")
    return number


def _bool(value: Any, name: str) -> bool:
    """Return one strict JSON boolean."""
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def _text(value: Any, name: str) -> str:
    """Return one non-empty JSON string."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _timestamp(value: Any) -> datetime:
    """Parse one timezone-aware snapshot timestamp."""
    text = _text(value, "recorded_at_utc")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("recorded_at_utc must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("recorded_at_utc must be timezone-aware")
    return parsed.astimezone(UTC)


def _digest(value: Any, name: str) -> str:
    """Validate one lowercase SHA-256 digest."""
    text = _text(value, name)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{name} must be lowercase SHA-256 hex")
    return text


def _limits_payload(limits: RuntimeContainmentLimits) -> dict[str, object]:
    """Return every configured containment limit without relying on dataclass internals."""
    return {
        "max_input_bytes": limits.max_input_bytes,
        "max_archive_members": limits.max_archive_members,
        "max_archive_uncompressed_bytes": limits.max_archive_uncompressed_bytes,
        "max_archive_compression_ratio": limits.max_archive_compression_ratio,
        "max_json_depth": limits.max_json_depth,
        "max_json_nodes": limits.max_json_nodes,
        "max_string_bytes": limits.max_string_bytes,
        "max_graph_nodes": limits.max_graph_nodes,
        "max_verification_seconds": limits.max_verification_seconds,
        "max_concurrency": limits.max_concurrency,
        "max_temporary_bytes": limits.max_temporary_bytes,
    }


def _parse_limits(payload: Any) -> RuntimeContainmentLimits:
    """Parse the exact containment-limit contract."""
    if not isinstance(payload, dict):
        raise ValueError("runtime_limits must be an object")
    expected = set(_limits_payload(RuntimeContainmentLimits()))
    _strict_keys(payload, expected=expected, name="runtime_limits")
    return RuntimeContainmentLimits(
        max_input_bytes=_int(payload["max_input_bytes"], "max_input_bytes", minimum=1),
        max_archive_members=_int(
            payload["max_archive_members"], "max_archive_members", minimum=1
        ),
        max_archive_uncompressed_bytes=_int(
            payload["max_archive_uncompressed_bytes"],
            "max_archive_uncompressed_bytes",
            minimum=1,
        ),
        max_archive_compression_ratio=_float(
            payload["max_archive_compression_ratio"],
            "max_archive_compression_ratio",
            minimum=1.0,
        ),
        max_json_depth=_int(payload["max_json_depth"], "max_json_depth", minimum=1),
        max_json_nodes=_int(payload["max_json_nodes"], "max_json_nodes", minimum=1),
        max_string_bytes=_int(
            payload["max_string_bytes"], "max_string_bytes", minimum=1
        ),
        max_graph_nodes=_int(payload["max_graph_nodes"], "max_graph_nodes", minimum=1),
        max_verification_seconds=_float(
            payload["max_verification_seconds"],
            "max_verification_seconds",
            minimum=0.000_000_1,
        ),
        max_concurrency=_int(payload["max_concurrency"], "max_concurrency", minimum=1),
        max_temporary_bytes=_int(
            payload["max_temporary_bytes"], "max_temporary_bytes", minimum=1
        ),
    )


@dataclass(frozen=True, slots=True)
class RuntimeContainmentConfigSnapshot:
    """Privacy-safe evidence of one effective verification-service configuration."""

    recorded_at_utc: datetime
    max_request_bytes: int
    read_only: bool
    require_https: bool
    allow_insecure_http: bool
    artifact_root_count: int
    runtime_limits: RuntimeContainmentLimits

    def __post_init__(self) -> None:
        """Validate configuration invariants represented by the snapshot."""
        if self.recorded_at_utc.tzinfo is None:
            raise ValueError("recorded_at_utc must be timezone-aware")
        if self.max_request_bytes <= 0:
            raise ValueError("max_request_bytes must be positive")
        if self.read_only is not True:
            raise ValueError("verification service snapshot must remain read-only")
        if self.artifact_root_count < 0:
            raise ValueError("artifact_root_count must be non-negative")
        if self.allow_insecure_http and self.require_https:
            raise ValueError("insecure HTTP opt-in conflicts with HTTPS requirement")

    def unsigned_payload(self) -> dict[str, object]:
        """Return the exact fields covered by the configuration digest."""
        return {
            "schema_version": RUNTIME_CONTAINMENT_SNAPSHOT_SCHEMA_VERSION,
            "recorded_at_utc": self.recorded_at_utc.astimezone(UTC).isoformat(),
            "verification_service": {
                "max_request_bytes": self.max_request_bytes,
                "read_only": self.read_only,
                "require_https": self.require_https,
                "allow_insecure_http": self.allow_insecure_http,
                "artifact_root_count": self.artifact_root_count,
                "artifact_roots_exposed": False,
            },
            "runtime_limits": _limits_payload(self.runtime_limits),
        }

    @property
    def configuration_digest(self) -> str:
        """Return the deterministic digest over the recorded effective configuration."""
        return hashlib.sha256(_canonical_json(self.unsigned_payload())).hexdigest()

    def to_dict(self) -> dict[str, object]:
        """Return the persisted strict snapshot contract."""
        payload = self.unsigned_payload()
        payload["configuration_digest"] = self.configuration_digest
        return payload

    @classmethod
    def capture(
        cls,
        *,
        max_request_bytes: int,
        read_only: bool,
        require_https: bool,
        allow_insecure_http: bool,
        artifact_root_count: int,
        runtime_limits: RuntimeContainmentLimits,
        recorded_at_utc: datetime | None = None,
    ) -> RuntimeContainmentConfigSnapshot:
        """Capture one effective service configuration without path or secret material."""
        return cls(
            recorded_at_utc=(recorded_at_utc or datetime.now(UTC)).astimezone(UTC),
            max_request_bytes=max_request_bytes,
            read_only=read_only,
            require_https=require_https,
            allow_insecure_http=allow_insecure_http,
            artifact_root_count=artifact_root_count,
            runtime_limits=runtime_limits,
        )


def write_runtime_containment_snapshot(
    path: Path,
    snapshot: RuntimeContainmentConfigSnapshot,
) -> None:
    """Atomically persist one effective runtime configuration snapshot."""
    target = path.expanduser()
    if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):
        raise ValueError("runtime containment snapshot path cannot traverse a symlink")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp")
    raw = _canonical_json(snapshot.to_dict()) + b"\n"
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_BINARY", 0)
    )
    try:
        fd = os.open(temp, flags, 0o600)
        try:
            offset = 0
            while offset < len(raw):
                offset += os.write(fd, raw[offset:])
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)


def load_runtime_containment_snapshot(
    path: Path,
    *,
    max_bytes: int,
) -> RuntimeContainmentConfigSnapshot:
    """Load and digest-verify one bounded runtime configuration snapshot."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    target = path.expanduser()
    if target.is_symlink() or any(parent.is_symlink() for parent in target.parents):
        raise ValueError("runtime containment snapshot path cannot traverse a symlink")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    fd = os.open(target, flags)
    try:
        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining > 0:
            chunk = os.read(fd, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
    finally:
        os.close(fd)
    if len(raw) > max_bytes:
        raise OverflowError(
            "runtime containment snapshot exceeds configured byte limit"
        )
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            "runtime containment snapshot is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError("runtime containment snapshot must be a JSON object")
    expected = {
        "schema_version",
        "recorded_at_utc",
        "verification_service",
        "runtime_limits",
        "configuration_digest",
    }
    _strict_keys(payload, expected=expected, name="runtime containment snapshot")
    if payload["schema_version"] != RUNTIME_CONTAINMENT_SNAPSHOT_SCHEMA_VERSION:
        raise ValueError("unsupported runtime containment snapshot schema version")
    service = payload["verification_service"]
    if not isinstance(service, dict):
        raise ValueError("verification_service must be an object")
    service_keys = {
        "max_request_bytes",
        "read_only",
        "require_https",
        "allow_insecure_http",
        "artifact_root_count",
        "artifact_roots_exposed",
    }
    _strict_keys(service, expected=service_keys, name="verification_service")
    if _bool(service["artifact_roots_exposed"], "artifact_roots_exposed") is not False:
        raise ValueError("runtime containment snapshot must not expose artifact roots")
    snapshot = RuntimeContainmentConfigSnapshot(
        recorded_at_utc=_timestamp(payload["recorded_at_utc"]),
        max_request_bytes=_int(
            service["max_request_bytes"], "max_request_bytes", minimum=1
        ),
        read_only=_bool(service["read_only"], "read_only"),
        require_https=_bool(service["require_https"], "require_https"),
        allow_insecure_http=_bool(
            service["allow_insecure_http"], "allow_insecure_http"
        ),
        artifact_root_count=_int(service["artifact_root_count"], "artifact_root_count"),
        runtime_limits=_parse_limits(payload["runtime_limits"]),
    )
    recorded_digest = _digest(payload["configuration_digest"], "configuration_digest")
    if recorded_digest != snapshot.configuration_digest:
        raise ValueError("runtime containment configuration digest mismatch")
    return snapshot


__all__ = [
    "RUNTIME_CONTAINMENT_SNAPSHOT_SCHEMA_VERSION",
    "RuntimeContainmentConfigSnapshot",
    "load_runtime_containment_snapshot",
    "write_runtime_containment_snapshot",
]
