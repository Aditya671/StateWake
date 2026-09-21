"""Regression checks for the executable release-candidate gate."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import scripts.release.verify_release_candidate as verifier
from config.project_paths import PROJECT_ROOT

ROOT = PROJECT_ROOT


def test_release_contract_matches_current_baseline() -> None:
    """Verify release identity and required release-candidate documents."""
    result = verifier.static_contract()
    assert result["status"] == "passed"


def test_tree_digest_is_deterministic() -> None:
    """Verify provenance hashing is stable for an unchanged source tree."""
    assert verifier.tree_digest() == verifier.tree_digest()


def test_failed_gate_is_not_recorded_as_passed() -> None:
    """Verify a non-zero gate becomes an explicit release failure."""
    with patch("scripts.release.verify_release_candidate.subprocess.run") as run:
        run.return_value.returncode = 7
        run.return_value.stdout = ""
        run.return_value.stderr = "failure"
        try:
            verifier.run_gate("synthetic", ["false"], timeout=1)
        except verifier.GateFailureError as exc:
            payload = json.loads(str(exc))
            assert payload["status"] == "failed"
            assert payload["returncode"] == 7
        else:
            raise AssertionError("failed release gate was accepted")


def test_tree_digest_excludes_generated_verification_evidence() -> None:
    """Generated verification evidence must not change the source identity digest."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "src").mkdir()
        (root / "src" / "module.py").write_text("value = 1\n", encoding="utf-8")
        with patch.object(verifier, "ROOT", root):
            before = verifier.tree_digest()
            (root / "verification").mkdir()
            (root / "verification" / "release-candidate-evidence.json").write_text(
                "{}\n", encoding="utf-8"
            )
            assert verifier.tree_digest() == before
