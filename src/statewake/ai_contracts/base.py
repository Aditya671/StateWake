"""Shared primitives for AI evidence contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import field
from datetime import UTC, datetime
from typing import Any

from statewake.domain.evidence import EvidenceItem
from statewake.utils.json_support import JsonValue, require_value

AI_CONTRACT_SCHEMA_VERSION = "statewake.ai_contract.v1"


def empty_metadata() -> dict[str, Any]:
    """Return a new mutable metadata mapping for dataclass defaults."""
    return {}


def metadata_field() -> Any:
    """Return the standard metadata dataclass field."""
    return field(default_factory=empty_metadata)


def require_non_empty(value: str, *, field_name: str) -> None:
    """Require a non-blank string field."""
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank.")


def require_optional_reason(
    value: str | None, *, reason: str | None, field_name: str
) -> None:
    """Require an explicit reason when an important optional field is omitted."""
    if value is None and (reason is None or not reason.strip()):
        raise ValueError(f"{field_name} requires an omission reason when omitted.")


def require_utc_datetime(value: datetime, *, field_name: str) -> None:
    """Require a timezone-aware UTC datetime for evidence capture fields."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
    if value.astimezone(UTC).utcoffset() != value.utcoffset():
        raise ValueError(f"{field_name} must be UTC.")


def datetime_to_json(value: datetime) -> str:
    """Serialize a datetime as a deterministic UTC ISO-8601 string."""
    require_utc_datetime(value, field_name="datetime")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def json_mapping(value: Mapping[str, Any], *, field_name: str) -> dict[str, JsonValue]:
    """Validate a dynamic mapping as JSON-compatible evidence metadata."""
    result: dict[str, JsonValue] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{field_name} keys must be non-blank strings.")
        result[key] = require_value(item, field=f"{field_name}.{key}")
    return dict(sorted(result.items()))


def canonical_json_bytes(payload: Mapping[str, JsonValue]) -> bytes:
    """Serialize a JSON object deterministically for digest binding."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(content: bytes) -> str:
    """Return the SHA-256 digest for content bytes."""
    return hashlib.sha256(content).hexdigest()


def evidence_item_from_payload(
    payload: Mapping[str, JsonValue],
    *,
    contract_type: str,
    producer_id: str,
    run_id: str,
    evidence_id: str | None = None,
    sensitivity: str = "internal",
) -> EvidenceItem:
    """Bind a contract payload into the existing StateWake evidence model."""
    digest = sha256_hex(canonical_json_bytes(payload))
    stable_id = evidence_id or f"ai-contract:{contract_type}:{run_id}:{digest[:16]}"
    return EvidenceItem(
        evidence_id=stable_id,
        source=f"statewake.ai_contracts.{contract_type}",
        digest=digest,
        content_ref=None,
        metadata={
            "contract_type": contract_type,
            "producer_id": producer_id,
            "run_id": run_id,
        },
        sensitivity=sensitivity,
    )
