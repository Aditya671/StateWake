"""Deterministic runtime containment contracts for untrusted evidence processing."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final
from urllib.parse import urlparse
from zipfile import ZipInfo

DEFAULT_MAX_INPUT_BYTES: Final[int] = 64 * 1024 * 1024


class ContainmentViolationError(ValueError):
    """Raised when untrusted input exceeds an explicit containment envelope."""


class MalformedJSONError(ContainmentViolationError):
    """Raised when a bounded JSON input is syntactically invalid."""


@dataclass(frozen=True, slots=True)
class RuntimeContainmentLimits:
    """Deployment-selectable limits for risky parsing and verification work."""

    max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES
    max_archive_members: int = 256
    max_archive_uncompressed_bytes: int = 128 * 1024 * 1024
    max_archive_compression_ratio: float = 100.0
    max_json_depth: int = 64
    max_json_nodes: int = 10_000
    max_string_bytes: int = 256 * 1024
    max_graph_nodes: int = 10_000
    max_verification_seconds: float = 30.0
    max_concurrency: int = 4
    max_temporary_bytes: int = 128 * 1024 * 1024

    def __post_init__(self) -> None:
        """Reject nonsensical or non-positive containment limits."""
        integer_fields = (
            "max_input_bytes",
            "max_archive_members",
            "max_archive_uncompressed_bytes",
            "max_json_depth",
            "max_json_nodes",
            "max_string_bytes",
            "max_graph_nodes",
            "max_concurrency",
            "max_temporary_bytes",
        )
        for name in integer_fields:
            value = getattr(self, name)
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        if self.max_archive_compression_ratio < 1.0:
            raise ValueError("max_archive_compression_ratio must be at least 1")
        if self.max_verification_seconds <= 0:
            raise ValueError("max_verification_seconds must be positive")


@dataclass(frozen=True, slots=True)
class VerificationDeadline:
    """Monotonic deadline used by cooperative verification loops."""

    expires_at: float

    @classmethod
    def from_limits(cls, limits: RuntimeContainmentLimits) -> VerificationDeadline:
        """Create a deadline from the configured verification-time envelope."""
        return cls(time.monotonic() + limits.max_verification_seconds)

    def check(self) -> None:
        """Raise when cooperative verification has exceeded its time envelope."""
        if time.monotonic() > self.expires_at:
            raise ContainmentViolationError("verification time envelope exceeded")


def validate_input_size(
    size: int, *, limits: RuntimeContainmentLimits, label: str = "input"
) -> None:
    """Reject an input whose byte size exceeds the configured envelope."""
    if size < 0:
        raise ContainmentViolationError(f"{label} size must be non-negative")
    if size > limits.max_input_bytes:
        raise ContainmentViolationError(
            f"{label} exceeds maximum input size of {limits.max_input_bytes} bytes"
        )


def _walk_json(
    value: object,
    *,
    depth: int,
    counts: list[int],
    limits: RuntimeContainmentLimits,
    path: str,
) -> None:
    """Walk decoded JSON while enforcing depth, node, and string limits."""
    counts[0] += 1
    if counts[0] > limits.max_json_nodes:
        raise ContainmentViolationError(
            f"JSON node count exceeds maximum of {limits.max_json_nodes}"
        )
    if depth > limits.max_json_depth:
        raise ContainmentViolationError(
            f"JSON nesting depth exceeds maximum of {limits.max_json_depth}"
        )
    if isinstance(value, str):
        if len(value.encode("utf-8")) > limits.max_string_bytes:
            raise ContainmentViolationError(
                f"JSON string at {path} exceeds maximum size of "
                f"{limits.max_string_bytes} bytes"
            )
        return
    if isinstance(value, dict):
        for key, child in value.items():
            if len(key.encode("utf-8")) > limits.max_string_bytes:
                raise ContainmentViolationError(
                    f"JSON key at {path} exceeds maximum size of "
                    f"{limits.max_string_bytes} bytes"
                )
            _walk_json(
                child,
                depth=depth + 1,
                counts=counts,
                limits=limits,
                path=f"{path}.{key}",
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_json(
                child,
                depth=depth + 1,
                counts=counts,
                limits=limits,
                path=f"{path}[{index}]",
            )


def load_bounded_json(
    payload: bytes | str, *, limits: RuntimeContainmentLimits, label: str = "JSON"
) -> object:
    """Decode JSON only after enforcing byte, depth, node, and string limits."""
    raw = payload.encode("utf-8") if isinstance(payload, str) else payload
    validate_input_size(len(raw), limits=limits, label=label)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MalformedJSONError(f"{label} is not valid JSON") from exc
    _walk_json(value, depth=0, counts=[0], limits=limits, path=label)
    return value


def validate_archive_metadata(
    info: ZipInfo, *, limits: RuntimeContainmentLimits
) -> None:
    """Reject unsafe ZIP metadata before reading a member body."""
    filename = PurePosixPath(info.filename)
    if filename.is_absolute() or ".." in filename.parts:
        raise ContainmentViolationError(f"unsafe archive path: {info.filename!r}")
    if info.file_size > limits.max_archive_uncompressed_bytes:
        raise ContainmentViolationError(
            f"archive member exceeds maximum size of "
            f"{limits.max_archive_uncompressed_bytes} bytes"
        )
    compressed = max(info.compress_size, 1)
    ratio = info.file_size / compressed
    if ratio > limits.max_archive_compression_ratio:
        raise ContainmentViolationError(
            "archive compression ratio exceeds containment limit"
        )
    external_mode = (info.external_attr >> 16) & 0xFFFF
    if external_mode and (external_mode & 0o170000) == 0o120000:
        raise ContainmentViolationError("archive symlinks are not permitted")


def validate_archive_envelope(
    infos: tuple[ZipInfo, ...], *, limits: RuntimeContainmentLimits
) -> None:
    """Validate archive member count and aggregate uncompressed size."""
    if len(infos) > limits.max_archive_members:
        raise ContainmentViolationError(
            f"archive contains more than {limits.max_archive_members} members"
        )
    total_size = 0
    for info in infos:
        validate_archive_metadata(info, limits=limits)
        total_size += info.file_size
        if total_size > limits.max_archive_uncompressed_bytes:
            raise ContainmentViolationError(
                "archive aggregate uncompressed size exceeds containment limit"
            )


def validate_reference(
    value: str, *, approved_schemes: frozenset[str] = frozenset()
) -> None:
    """Reject arbitrary network references unless their scheme is explicitly allowed."""
    parsed = urlparse(value)
    if not parsed.scheme:
        return
    if parsed.scheme.lower() not in approved_schemes:
        raise ContainmentViolationError(
            f"external reference scheme is not approved: {parsed.scheme.lower()}"
        )


__all__ = [
    "ContainmentViolationError",
    "MalformedJSONError",
    "DEFAULT_MAX_INPUT_BYTES",
    "RuntimeContainmentLimits",
    "VerificationDeadline",
    "load_bounded_json",
    "validate_archive_envelope",
    "validate_archive_metadata",
    "validate_input_size",
    "validate_reference",
]
