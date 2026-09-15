"""Typed helpers for JSON boundaries used throughout StateWake."""

from __future__ import annotations

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypeAlias

JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | dict[str, "JsonValue"] | list["JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


def require_object(value: object, *, field: str = "payload") -> Mapping[str, JsonValue]:
    """Return a JSON object after validating its runtime shape."""
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a JSON object.")
    result: dict[str, JsonValue] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{field} keys must be strings.")
        result[key] = require_value(item, field=f"{field}.{key}")
    return result


def require_value(value: object, *, field: str = "value") -> JsonValue:
    """Validate and return one JSON-compatible value."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Mapping):
        return dict(require_object(value, field=field))
    if isinstance(value, list):
        return [require_value(item, field=field) for item in value]
    raise ValueError(f"{field} contains a non-JSON value.")


def loads_object(
    value: str | bytes | bytearray, *, field: str = "payload"
) -> Mapping[str, JsonValue]:
    """Decode JSON and validate that its top-level value is an object."""
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field} must contain valid JSON.") from exc
    return require_object(decoded, field=field)


def load_object(path: Path, *, field: str = "payload") -> Mapping[str, JsonValue]:
    """Read a UTF-8 JSON document and validate its top-level object shape."""
    return loads_object(path.read_text(encoding="utf-8"), field=field)


def require_bool(value: object, *, field: str) -> bool:
    """Return a JSON boolean after validating its runtime type."""
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a JSON boolean.")
    return value


def require_int(value: object, *, field: str) -> int:
    """Return a JSON integer, rejecting booleans and other scalar types."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{field} must be a JSON integer.")
    return value


def require_string(value: object, *, field: str) -> str:
    """Return a JSON string after validating its runtime type."""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a JSON string.")
    return value


def string_mapping(value: object, *, field: str = "metadata") -> dict[str, str]:
    """Return a string-to-string mapping from a JSON mapping boundary."""
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a JSON object.")
    return {str(key): str(item) for key, item in value.items()}


def string_sequence(value: object, *, field: str) -> tuple[str, ...]:
    """Return a tuple of strings from a JSON array-like boundary."""
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise ValueError(f"{field} must be a JSON array.")
    return tuple(str(item) for item in value)


def metadata_from_cli(values: Sequence[str]) -> dict[str, str]:
    """Parse repeated ``key=value`` CLI metadata arguments."""
    metadata: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise ValueError(f"metadata must use key=value syntax: {item!r}")
        key, value = item.split("=", 1)
        if not key.strip():
            raise ValueError("metadata key must not be blank.")
        metadata[key] = value
    return metadata


__all__ = [
    "JsonObject",
    "JsonPrimitive",
    "JsonValue",
    "load_object",
    "loads_object",
    "metadata_from_cli",
    "require_bool",
    "require_int",
    "require_string",
    "require_object",
    "require_value",
    "string_mapping",
    "string_sequence",
]
