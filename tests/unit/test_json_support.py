"""Tests for typed JSON-boundary utility helpers."""

from pathlib import Path

import pytest

from statewake.utils.json_support import (
    load_object,
    loads_object,
    metadata_from_cli,
    require_object,
    string_mapping,
    string_sequence,
)


def test_loads_object_validates_and_preserves_json_shape() -> None:
    """Decode a JSON object without introducing unknown mapping types."""
    payload = loads_object('{"metadata":{"attempt":3},"items":["a", "b"]}')

    assert payload["metadata"] == {"attempt": 3}
    assert payload["items"] == ["a", "b"]


def test_load_object_reads_utf8_json_document(tmp_path: Path) -> None:
    """Read a JSON object from a UTF-8 file."""
    path = tmp_path / "payload.json"
    path.write_text('{"name":"statewake"}', encoding="utf-8")

    assert load_object(path)["name"] == "statewake"


def test_require_object_rejects_non_object_values() -> None:
    """Reject JSON values that cannot satisfy an object contract."""
    with pytest.raises(ValueError, match="payload must be a JSON object"):
        require_object(["not", "an", "object"])


def test_string_mapping_normalizes_metadata_boundary() -> None:
    """Convert metadata values into the domain's explicit string contract."""
    assert string_mapping({"attempt": 3, "enabled": True}) == {
        "attempt": "3",
        "enabled": "True",
    }


def test_string_sequence_normalizes_array_boundary() -> None:
    """Convert an array-like JSON boundary into immutable string values."""
    assert string_sequence([1, "two"], field="values") == ("1", "two")


def test_metadata_from_cli_preserves_equals_in_value() -> None:
    """Parse repeated CLI metadata without losing embedded equals signs."""
    assert metadata_from_cli(["run=42", "query=a=b"]) == {
        "run": "42",
        "query": "a=b",
    }


def test_metadata_from_cli_rejects_malformed_entry() -> None:
    """Reject metadata entries that omit the required equals separator."""
    from statewake.utils.json_support import metadata_from_cli

    with pytest.raises(ValueError, match="key=value"):
        metadata_from_cli(["environment=ci", "malformed"])


def test_metadata_from_cli_rejects_blank_key() -> None:
    """Reject metadata entries with an empty key."""
    from statewake.utils.json_support import metadata_from_cli

    with pytest.raises(ValueError, match="key"):
        metadata_from_cli(["=value"])
