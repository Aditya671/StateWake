"""Validation helpers for serialized AI evidence contracts."""

from __future__ import annotations

from collections.abc import Mapping

from statewake.ai_contracts.base import AI_CONTRACT_SCHEMA_VERSION
from statewake.utils.json_support import JsonValue

REQUIRED_BASE_FIELDS = frozenset(
    {
        "schema_version",
        "contract_type",
        "contract_version",
        "producer_id",
        "run_id",
        "captured_at",
    }
)


def validate_contract_payload(payload: Mapping[str, JsonValue]) -> None:
    """Validate the common serialized shape shared by all AI contracts."""
    missing = sorted(REQUIRED_BASE_FIELDS - payload.keys())
    if missing:
        raise ValueError("AI contract payload missing: " + ", ".join(missing))
    if payload["schema_version"] != AI_CONTRACT_SCHEMA_VERSION:
        raise ValueError("unsupported AI contract schema_version.")
    for field_name in ("contract_type", "contract_version", "producer_id", "run_id"):
        value = payload[field_name]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-blank string.")
