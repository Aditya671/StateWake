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
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
    ).hexdigest()


def redacted_payload_reference(
    payload: Mapping[str, Any], *, sensitive_keys: frozenset[str] = SENSITIVE_KEYS
) -> dict[str, Any]:
    """Return a redacted inspection payload while preserving the original digest."""
    digest = canonical_payload_digest(payload)
    visible: dict[str, Any] = {}
    redacted_keys: list[str] = []
    for key, value in sorted(payload.items()):
        if key in sensitive_keys:
            visible[key] = "<redacted>"
            redacted_keys.append(key)
        else:
            visible[key] = value
    return {
        "payload_digest": digest,
        "redacted": bool(redacted_keys),
        "redacted_keys": redacted_keys,
        "visible": visible,
    }


__all__ = ["SENSITIVE_KEYS", "canonical_payload_digest", "redacted_payload_reference"]
