"""Regression tests for Tier 12 runtime and hostile-input containment."""

from __future__ import annotations

import json
import time
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest

from statewake.domain.runtime_containment import (
    ContainmentViolationError,
    RuntimeContainmentLimits,
    VerificationDeadline,
    load_bounded_json,
    validate_archive_envelope,
    validate_reference,
)


def test_rejects_oversized_input() -> None:
    """Reject bytes beyond the configured input envelope."""
    limits = RuntimeContainmentLimits(max_input_bytes=4)
    with pytest.raises(ContainmentViolationError, match="maximum input size"):
        load_bounded_json(b'{"a":1}', limits=limits)


def test_rejects_deep_json() -> None:
    """Reject deeply nested JSON structures."""
    limits = RuntimeContainmentLimits(max_json_depth=3)
    payload = json.dumps({"a": {"b": {"c": {"d": 1}}}}).encode()
    with pytest.raises(ContainmentViolationError, match="nesting depth"):
        load_bounded_json(payload, limits=limits)


def test_rejects_excessive_json_nodes() -> None:
    """Reject JSON with more nodes than the configured envelope."""
    limits = RuntimeContainmentLimits(max_json_nodes=5)
    with pytest.raises(ContainmentViolationError, match="node count"):
        load_bounded_json(b"[1,2,3,4,5,6]", limits=limits)


def test_rejects_oversized_string() -> None:
    """Reject an oversized attacker-controlled JSON string."""
    limits = RuntimeContainmentLimits(max_string_bytes=4)
    with pytest.raises(ContainmentViolationError, match="string"):
        load_bounded_json(b'{"x":"12345"}', limits=limits)


def _zip_with_member(tmp_path: Path, name: str, data: bytes) -> Path:
    """Create one ZIP fixture with a deterministic member."""
    path = tmp_path / "fixture.zip"
    with ZipFile(path, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        archive.writestr(name, data)
    return path


def test_rejects_archive_ratio(tmp_path: Path) -> None:
    """Reject an archive member with excessive compression ratio."""
    path = _zip_with_member(tmp_path, "payload.bin", b"x" * 8192)
    with ZipFile(path) as archive:
        limits = RuntimeContainmentLimits(max_archive_compression_ratio=2.0)
        with pytest.raises(ContainmentViolationError, match="compression ratio"):
            validate_archive_envelope(tuple(archive.infolist()), limits=limits)


def test_rejects_archive_expansion(tmp_path: Path) -> None:
    """Reject aggregate archive expansion beyond the configured envelope."""
    path = tmp_path / "aggregate.zip"
    with ZipFile(path, "w", compression=ZIP_DEFLATED, compresslevel=1) as archive:
        archive.writestr("one.bin", b"x" * 400)
        archive.writestr("two.bin", b"y" * 400)
    with ZipFile(path) as archive:
        limits = RuntimeContainmentLimits(
            max_archive_compression_ratio=10_000,
            max_archive_uncompressed_bytes=700,
        )
        with pytest.raises(ContainmentViolationError, match="aggregate"):
            validate_archive_envelope(tuple(archive.infolist()), limits=limits)


def test_rejects_archive_traversal(tmp_path: Path) -> None:
    """Reject archive paths containing parent traversal."""
    path = _zip_with_member(tmp_path, "../escape.txt", b"unsafe")
    with ZipFile(path) as archive:
        with pytest.raises(ContainmentViolationError, match="unsafe archive path"):
            validate_archive_envelope(
                tuple(archive.infolist()), limits=RuntimeContainmentLimits()
            )


def test_rejects_archive_symlink(tmp_path: Path) -> None:
    """Reject ZIP symlink entries before member reads."""
    path = tmp_path / "symlink.zip"
    info = ZipInfo("link")
    info.external_attr = (0o120777 << 16) | 0x000A
    with ZipFile(path, "w") as archive:
        archive.writestr(info, b"target")
    with ZipFile(path) as archive:
        with pytest.raises(ContainmentViolationError, match="symlink"):
            validate_archive_envelope(
                tuple(archive.infolist()), limits=RuntimeContainmentLimits()
            )


def test_rejects_external_reference() -> None:
    """Reject URI schemes unless explicitly approved."""
    with pytest.raises(ContainmentViolationError, match="external reference scheme"):
        validate_reference("https://example.test/resource")
    validate_reference("local-reference")


def test_deadline_is_bounded() -> None:
    """Raise once cooperative verification exceeds its configured deadline."""
    limits = RuntimeContainmentLimits(max_verification_seconds=0.001)
    deadline = VerificationDeadline.from_limits(limits)
    time.sleep(0.005)
    with pytest.raises(ContainmentViolationError, match="time envelope"):
        deadline.check()


def test_server_uses_bounded_json_loader() -> None:
    """Confirm the HTTP adapter uses the containment loader at its JSON boundary."""
    source = Path(__file__).parents[1] / "src/statewake/server.py"
    text = source.read_text(encoding="utf-8")
    assert "load_bounded_json(raw" in text
    assert "runtime_limits" in text


def test_archive_verification_does_not_execute_members(tmp_path: Path) -> None:
    """Verify an archive containing executable-looking data is treated only as bytes."""
    from statewake.services.operations_service import verify_bundle

    path = tmp_path / "executable-looking.zip"
    manifest = {
        "bundle_id": "invalid",
        "manifest_id": "invalid",
        "agent_name": "test",
        "engine_version": "0.1.0",
        "created_at": "2026-09-16T00:00:00+00:00",
        "artifacts": [],
    }
    with ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("payload.sh", b"#!/bin/sh\ntouch /tmp/statewake-executed")
    with pytest.raises(ValueError):
        verify_bundle(path)
    assert not Path("/tmp/statewake-executed").exists()


def test_portable_verifier_rejects_network_reference() -> None:
    """Require the portable verifier to reject arbitrary URI sources."""
    from scripts.security.verify_reliability_proof_portability import validate_reference

    with pytest.raises(ValueError, match="external reference scheme"):
        validate_reference("https://example.test/resource")

    validate_reference("local-artifact")


def test_server_rejects_malformed_json_with_bad_request() -> None:
    """Preserve the HTTP adapter's malformed-JSON status contract."""
    from tempfile import TemporaryDirectory

    from statewake.server import VerificationServiceConfig, create_application

    with TemporaryDirectory() as directory:
        config = VerificationServiceConfig(artifact_roots=(Path(directory),))
        application = create_application(config)
        captured: dict[str, object] = {}

        def start_response(status: str, headers: list[tuple[str, str]]) -> None:
            captured["status"] = status
            captured["headers"] = headers

        malformed = b"{not-json"
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/v1/evidence/verify",
            "CONTENT_LENGTH": str(len(malformed)),
            "wsgi.input": __import__("io").BytesIO(malformed),
            "wsgi.url_scheme": "https",
        }
        body = b"".join(application(environ, start_response))  # type: ignore
        assert captured["status"] == "400 Bad Request"
        assert json.loads(body)["error"]["code"] == "INVALID_JSON"
