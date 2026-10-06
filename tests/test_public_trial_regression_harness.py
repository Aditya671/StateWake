"""Tests for the frozen public-repository trial regression coordinator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.common.project_paths import PROJECT_ROOT
from scripts.testing.run_public_trial_regressions import ALLOWED_OUTCOMES, load_manifest

MANIFEST = PROJECT_ROOT / "tests/fixtures/public_trial_regression_manifest.json"


def test_manifest_preserves_all_repaired_public_trial_capabilities() -> None:
    cases = load_manifest(MANIFEST)
    anomalies = {case.anomaly for case in cases}
    assert {
        "SW-INT-01",
        "SW-INT-02",
        "SW-INT-03+SW-INT-04",
        "SW-PKG-01",
        "SW-PY-01",
    } <= anomalies
    assert any(case.anomaly == "NON_REGRESSION" for case in cases)


def test_manifest_uses_campaign_outcome_vocabulary() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert set(payload["outcomes"]) == ALLOWED_OUTCOMES


def test_manifest_pins_real_upstream_commits_and_existing_tests() -> None:
    for case in load_manifest(MANIFEST):
        assert len(case.commit) == 40
        assert case.source_tests
        for target in case.source_tests:
            assert (PROJECT_ROOT / target.split("::", 1)[0]).is_file()


def test_manifest_rejects_duplicate_case_ids(tmp_path: Path) -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))
    payload["cases"].append(dict(payload["cases"][0]))
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="case_id"):
        load_manifest(path)


def test_sdk_cases_have_dedicated_native_qualification_targets() -> None:
    """Keep source regressions separate from required real-SDK probes."""
    sdk_cases = [
        case for case in load_manifest(MANIFEST) if case.qualification_requires_sdk
    ]
    assert {case.case_id for case in sdk_cases} == {
        "OA-RESPONSES-001",
        "LC-RAG-SYNTHETIC-001",
        "LG-STARTER-CHECKPOINT-002",
        "LI-RAG-ROOT-DIAGNOSTIC-002",
        "OTEL-GENAI-SPAN-001",
    }
    assert all(case.qualification_tests for case in sdk_cases)
    assert any(
        "test_real_openai_agents_native_span_lifecycle" in target
        for target in sdk_cases[0].qualification_tests
    )


def test_qualification_status_never_promotes_missing_or_skipped_sdk() -> None:
    """Missing SDKs block; installed-but-skipped native probes fail integration."""
    from scripts.testing.run_public_trial_regressions import (
        DependencyEvidence,
        PytestEvidence,
        _qualification_status,
    )

    case = next(
        item for item in load_manifest(MANIFEST) if item.case_id == "OA-RESPONSES-001"
    )
    blocked, reason = _qualification_status(
        case,
        dependencies=(
            DependencyEvidence(
                "openai-agents>=0.3,<1", "openai-agents", "MISSING", None
            ),
        ),
        qualification=None,
    )
    assert blocked == "BLOCKED_ENV"
    assert reason is not None and "openai-agents" in reason

    failed, reason = _qualification_status(
        case,
        dependencies=(
            DependencyEvidence(
                "openai-agents>=0.3,<1", "openai-agents", "INSTALLED", "0.22.3"
            ),
        ),
        qualification=PytestEvidence("PASS", 0, 1, False, "1 skipped", "", None),
    )
    assert failed == "FAIL_INTEGRATION"
    assert reason is not None and "skipped" in reason


def test_qualification_status_accepts_only_executed_native_probe() -> None:
    """An installed SDK qualifies only after the dedicated probe really passes."""
    from scripts.testing.run_public_trial_regressions import (
        DependencyEvidence,
        PytestEvidence,
        _qualification_status,
    )

    case = next(
        item
        for item in load_manifest(MANIFEST)
        if item.case_id == "LG-STARTER-CHECKPOINT-002"
    )
    status, reason = _qualification_status(
        case,
        dependencies=(
            DependencyEvidence("langgraph>=0.3,<2", "langgraph", "INSTALLED", "1.2.12"),
        ),
        qualification=PytestEvidence("PASS", 0, 0, False, "1 passed", "", None),
    )
    assert status == "PASS"
    assert reason is None


def test_native_qualification_report_is_bounded_and_versioned() -> None:
    """The report exposes versions/status, not captured framework payloads."""
    from scripts.testing.run_public_trial_regressions import _render_report

    report = _render_report(
        {
            "mode": "qualification",
            "status": "BLOCKED_ENV",
            "python_version": "3.13.5",
            "python_executable": "/tmp/python",
            "results": [
                {
                    "case_id": "OA-RESPONSES-001",
                    "status": "BLOCKED_ENV",
                    "qualification_status": "BLOCKED_ENV",
                    "dependencies": [
                        {
                            "distribution": "openai-agents",
                            "installed_version": None,
                        }
                    ],
                }
            ],
        }
    )
    assert "openai-agents=missing" in report
    assert "Publication authorized: **No**" in report
    assert "stdout" not in report
    assert "stderr" not in report
