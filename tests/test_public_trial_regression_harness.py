"""Tests for the frozen public-repository trial regression coordinator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.project_paths import PROJECT_ROOT
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
