"""Deterministic serialization helpers for AI evidence contracts."""

from __future__ import annotations

import json
from collections.abc import Mapping

from statewake.ai_contracts.base import canonical_json_bytes, sha256_hex
from statewake.utils.json_support import JsonValue, loads_object


def contract_to_json_bytes(payload: Mapping[str, JsonValue]) -> bytes:
    """Serialize a contract payload deterministically."""
    return canonical_json_bytes(payload)


def contract_digest(payload: Mapping[str, JsonValue]) -> str:
    """Return the digest of a deterministic contract payload."""
    return sha256_hex(contract_to_json_bytes(payload))


def contract_from_json_bytes(content: bytes) -> Mapping[str, JsonValue]:
    """Load and runtime-validate a serialized AI evidence contract."""
    return loads_object(content, field="ai_contract")


def pretty_contract_json(payload: Mapping[str, JsonValue]) -> str:
    """Render stable pretty JSON for reports and human inspection."""
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"
