"""Tests for credential-free external integration capture handling."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.integration.run_external_integrations as external_integrations
from config.project_paths import PROJECT_ROOT
from scripts.integration.run_external_integrations import ingest_capture, load_fixture

ROOT = PROJECT_ROOT
FIXTURES = ROOT / "tests" / "fixtures" / "external_captures"


def test_external_fixtures_declare_capture_scope_and_hash() -> None:
    """Verify fixtures state their representation and bind bytes to a digest."""
    fixtures = sorted(FIXTURES.glob("*.json"))
    assert len(fixtures) >= 3
    for fixture in fixtures:
        capture = load_fixture(fixture)
        assert capture.source_url.startswith("https://")
        assert capture.reference
        assert capture.reference_kind
        assert capture.capture_kind == "bounded_projection"
        assert (
            capture.capture_scope
            == "stored_payload_is_bounded_projection_not_full_external_response"
        )
        assert capture.content
        assert hashlib.sha256(capture.content).hexdigest() == capture.content_sha256


def test_external_capture_reaches_statewake(tmp_path: Path) -> None:
    """Verify one externally sourced projection crosses the public SDK boundary."""
    capture = load_fixture(FIXTURES / "github-stripe-starter.json")
    result = ingest_capture(capture, tmp_path)
    assert result["verified"] is True
    assert result["artifact_sha256"] == capture.content_sha256
    assert result["capture_scope"] == capture.capture_scope
    assert result["receipt_id"]


def test_external_ci_mode_works_from_repository_root() -> None:
    """Verify the standalone external integration script resolves the src layout."""
    result = subprocess.run(
        [
            sys.executable,
            "scripts/integration/run_external_integrations.py",
            "--mode",
            "ci",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"
    assert all(item["verified"] for item in payload["results"])


def test_live_mode_reports_failed_target_identity(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Identify each live target when an external dependency is unavailable."""

    def fail_github() -> external_integrations.ExternalCapture:
        raise OSError("dns unavailable")

    def fail_municipal() -> external_integrations.ExternalCapture:
        raise ValueError("unexpected response")

    monkeypatch.setattr(external_integrations, "capture_public_github", fail_github)
    monkeypatch.setattr(
        external_integrations, "capture_public_municipal", fail_municipal
    )
    monkeypatch.setattr(sys, "argv", ["run_external_integrations.py", "--mode", "live"])

    assert external_integrations.main() == 3
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "LIVE_EXTERNAL_GATE_BLOCKED"
    assert {item["target"] for item in payload["failures"]} == {"github", "municipal"}


def test_external_fixture_tampering_is_rejected(tmp_path: Path) -> None:
    """Reject a fixture whose recorded digest no longer matches its payload."""
    path = tmp_path / "tampered.json"
    payload = json.loads(
        (FIXTURES / "github-stripe-starter.json").read_text(encoding="utf-8")
    )
    payload["content_hex"] = (
        "00" if payload["content_hex"][:2] != "00" else "01"
    ) + payload["content_hex"][2:]
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="content_sha256"):
        load_fixture(path)
