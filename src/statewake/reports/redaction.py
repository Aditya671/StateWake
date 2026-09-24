"""Redaction helpers for reports that must preserve verifiability."""

from __future__ import annotations

import json
from collections.abc import Mapping
from hashlib import sha256
from typing import Any

SENSITIVE_KEYS = frozenset(
    {
        "raw_prompt",
        "prompt",
        "completion",
        "tool_input",
        "tool_output",
        "secret",
        "token",
        "password",
        "api_key",
    }
)


def canonical_payload_digest(payload: Mapping[str, Any]) -> str:
    """Return a deterministic digest for a JSON-compatible payload."""
    return sha256(
        json.dumps(
            payload, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def redacted_payload_reference(
    payload: Mapping[str, Any], *, sensitive_keys: frozenset[str] = SENSITIVE_KEYS
) -> dict[str, Any]:
    """Return a redacted inspection payload while preserving the original digest."""
    digest = canonical_payload_digest(payload)
    redacted_keys: list[str] = []

    def redact(value: Any, location: str) -> Any:
        if isinstance(value, Mapping):
            visible: dict[str, Any] = {}
            for key, child in sorted(value.items()):
                if not isinstance(key, str):
                    raise ValueError("redaction payload keys must be strings")
                path = f"{location}.{key}" if location else key
                normalized = key.lower().replace("-", "_").replace(".", "_")
                if normalized in sensitive_keys or any(
                    marker in normalized
                    for marker in ("api_key", "password", "secret", "token")
                ):
                    visible[key] = "<redacted>"
                    redacted_keys.append(path)
                else:
                    visible[key] = redact(child, path)
            return visible
        if isinstance(value, (list, tuple)):
            return [
                redact(child, f"{location}[{index}]")
                for index, child in enumerate(value)
            ]
        return value

    visible = redact(payload, "")
    return {
        "payload_digest": digest,
        "redacted": bool(redacted_keys),
        "redacted_keys": redacted_keys,
        "visible": visible,
    }


__all__ = ["SENSITIVE_KEYS", "canonical_payload_digest", "redacted_payload_reference"]
