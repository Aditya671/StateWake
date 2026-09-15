"""Regression tests for the bounded verification HTTP adapter."""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
import io
import json
from pathlib import Path
from typing import Any

from pytest import MonkeyPatch

from statewake import __version__
from statewake.server import VerificationServiceConfig, create_application


def request(
    application,
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    *,
    scheme: str = "http",
):
    body = b"" if payload is None else json.dumps(payload).encode()
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(body)),
        "wsgi.input": io.BytesIO(body),
        "wsgi.url_scheme": scheme,
    }
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = headers

    raw = b"".join(application(environ, start_response))
    return captured["status"], json.loads(raw)


def test_http_health_and_version():
    application = create_application(
        VerificationServiceConfig(allow_insecure_http=True)
    )
    assert request(application, "/health") == (
        "200 OK",
        {"status": "ok", "version": __version__},
    )
    assert request(application, "/v1/version") == ("200 OK", {"version": __version__})


def test_http_unknown_route():
    application = create_application(
        VerificationServiceConfig(allow_insecure_http=True)
    )
    status, payload = request(application, "/missing")
    assert status == "404 Not Found"
    assert payload == {"error": {"code": "NOT_FOUND", "message": "not found"}}


def test_http_verification_requires_https_by_default(tmp_path: Path):
    application = create_application(
        VerificationServiceConfig(artifact_roots=(tmp_path,))
    )
    status, payload = request(
        application,
        "/v1/evidence/verify",
        "POST",
        {"chain_path": str(tmp_path / "chain.json"), "evidence_root": str(tmp_path)},
    )
    assert status == "400 Bad Request"
    assert payload["error"]["code"] == "HTTPS_REQUIRED"


def test_http_rejects_paths_outside_configured_roots(tmp_path: Path):
    application = create_application(
        VerificationServiceConfig(artifact_roots=(tmp_path,), allow_insecure_http=True)
    )
    outside = tmp_path.parent / "outside.json"
    status, payload = request(
        application,
        "/v1/evidence/verify",
        "POST",
        {"chain_path": str(outside), "evidence_root": str(tmp_path)},
    )
    assert status == "403 Forbidden"
    assert payload["error"]["code"] == "PATH_OUTSIDE_ROOT"


def test_http_rejects_oversized_request(tmp_path: Path):
    application = create_application(
        VerificationServiceConfig(
            artifact_roots=(tmp_path,), max_request_bytes=10, allow_insecure_http=True
        )
    )
    status, payload = request(
        application,
        "/v1/evidence/verify",
        "POST",
        {"chain_path": "x", "evidence_root": "x"},
    )
    assert status == "413 Request Entity Too Large"
    assert payload["error"]["code"] == "REQUEST_TOO_LARGE"


def request_raw(
    application,
    path: str,
    method: str = "POST",
    raw_body: bytes = b"",
    *,
    scheme: str = "https",
):
    environ = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(raw_body)),
        "wsgi.input": io.BytesIO(raw_body),
        "wsgi.url_scheme": scheme,
    }
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = headers

    raw = b"".join(application(environ, start_response))
    return captured["status"], json.loads(raw)


def test_http_valid_evidence_endpoint(tmp_path: Path, monkeypatch: MonkeyPatch):
    application = create_application(
        VerificationServiceConfig(artifact_roots=(tmp_path,))
    )

    class Chain:
        chain_id = "chain-1"

        def digest(self):
            return "d" * 64

    monkeypatch.setattr("statewake.server.load_evidence_chain", lambda path: Chain())  # type: ignore
    monkeypatch.setattr(
        "statewake.server.verify_evidence_chain",
        lambda chain, root: None,  # type: ignore
    )
    status, payload = request(
        application,
        "/v1/evidence/verify",
        "POST",
        {
            "chain_path": str(tmp_path / "chain.json"),
            "evidence_root": str(tmp_path),
        },
        scheme="https",
    )
    assert status == "200 OK"
    assert payload == {"verified": True, "chain_id": "chain-1", "digest": "d" * 64}


def test_http_valid_proof_endpoint(tmp_path: Path, monkeypatch: MonkeyPatch):
    application = create_application(
        VerificationServiceConfig(artifact_roots=(tmp_path,))
    )

    class Report:
        verified = True
        checks = ("integrity",)
        failures = ()

    class Descriptor:
        bundle_type = "reliability-proof"
        subject_id = "agent-1"
        attestation_id = "att-1"

    monkeypatch.setattr(
        "statewake.server.verify_reliability_proof_bundle",
        lambda path: (Report(), Descriptor()),  # type: ignore
    )
    status, payload = request(
        application,
        "/v1/proof/verify",
        "POST",
        {
            "bundle_path": str(tmp_path / "proof.zip"),
        },
        scheme="https",
    )
    assert status == "200 OK"
    assert payload["verified"] is True
    assert payload["checks"] == ["integrity"]
    assert payload["failures"] == []


def test_http_rejects_malformed_json(tmp_path: Path):
    application = create_application(
        VerificationServiceConfig(artifact_roots=(tmp_path,))
    )
    status, payload = request_raw(application, "/v1/evidence/verify", raw_body=b"{bad")
    assert status == "400 Bad Request"
    assert payload == {
        "error": {"code": "INVALID_JSON", "message": "request body is not valid JSON"}
    }


def test_http_reports_missing_artifact(tmp_path: Path):
    application = create_application(
        VerificationServiceConfig(artifact_roots=(tmp_path,))
    )
    status, payload = request(
        application,
        "/v1/evidence/verify",
        "POST",
        {
            "chain_path": str(tmp_path / "missing.json"),
            "evidence_root": str(tmp_path),
        },
        scheme="https",
    )
    assert status == "404 Not Found"
    assert payload == {
        "error": {
            "code": "ARTIFACT_NOT_FOUND",
            "message": "referenced verification artifact was not found",
        }
    }


def test_http_rejects_symlink_escape(tmp_path: Path):
    outside = tmp_path.parent / "outside-statewake-artifact.json"
    outside.write_text("{}", encoding="utf-8")
    link = tmp_path / "chain.json"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        return
    application = create_application(
        VerificationServiceConfig(artifact_roots=(tmp_path,))
    )
    status, payload = request(
        application,
        "/v1/evidence/verify",
        "POST",
        {
            "chain_path": str(link),
            "evidence_root": str(tmp_path),
        },
        scheme="https",
    )
    assert status == "403 Forbidden"
    assert payload == {
        "error": {
            "code": "PATH_OUTSIDE_ROOT",
            "message": "artifact path is outside configured verification roots",
        }
    }


def test_http_sanitizes_internal_validation_errors(
    tmp_path: Path, monkeypatch: MonkeyPatch
):
    application = create_application(
        VerificationServiceConfig(artifact_roots=(tmp_path,))
    )

    def fail(*args, **kwargs):
        raise ValueError(f"internal path {tmp_path / 'secret.json'} should not leak")

    monkeypatch.setattr("statewake.server.load_evidence_chain", fail)
    status, payload = request(
        application,
        "/v1/evidence/verify",
        "POST",
        {
            "chain_path": str(tmp_path / "chain.json"),
            "evidence_root": str(tmp_path),
        },
        scheme="https",
    )
    assert status == "422 Unprocessable Entity"
    assert payload == {
        "error": {
            "code": "INVALID_REQUEST",
            "message": "verification request is invalid",
        }
    }
    assert "secret.json" not in json.dumps(payload)


def test_http_rejects_tampered_evidence_with_stable_error(
    tmp_path: Path, monkeypatch: MonkeyPatch
):
    application = create_application(
        VerificationServiceConfig(artifact_roots=(tmp_path,))
    )

    def fail(*args, **kwargs):
        raise ValueError("artifact digest mismatch for /srv/private/chain.json")

    monkeypatch.setattr("statewake.server.verify_evidence_chain", fail)
    monkeypatch.setattr("statewake.server.load_evidence_chain", lambda path: object())  # type: ignore
    status, payload = request(
        application,
        "/v1/evidence/verify",
        "POST",
        {
            "chain_path": str(tmp_path / "chain.json"),
            "evidence_root": str(tmp_path),
        },
        scheme="https",
    )
    assert status == "422 Unprocessable Entity"
    assert payload == {
        "error": {
            "code": "INVALID_REQUEST",
            "message": "verification request is invalid",
        }
    }


def test_http_returns_unverified_proof_as_422(tmp_path: Path, monkeypatch: MonkeyPatch):
    application = create_application(
        VerificationServiceConfig(artifact_roots=(tmp_path,))
    )

    class Report:
        verified = False
        checks = ("integrity",)
        failures = ("digest mismatch",)

    class Descriptor:
        bundle_type = "reliability-proof"
        subject_id = "agent-1"
        attestation_id = "att-1"

    monkeypatch.setattr(
        "statewake.server.verify_reliability_proof_bundle",
        lambda path: (Report(), Descriptor()),  # type: ignore
    )
    status, payload = request(
        application,
        "/v1/proof/verify",
        "POST",
        {
            "bundle_path": str(tmp_path / "proof.zip"),
        },
        scheme="https",
    )
    assert status == "422 Unprocessable Entity"
    assert payload["verified"] is False
    assert payload["failures"] == ["digest mismatch"]
