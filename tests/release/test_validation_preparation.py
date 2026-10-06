"""Regression tests for deterministic SDLC validation preparation."""

from __future__ import annotations

import sys
from typing import cast
from unittest.mock import call, patch

from scripts.release import prepare_sdlc_validation as preparation


def test_preparation_refreshes_only_release_identity_and_verifies_other_authorities() -> (
    None
):
    """Preparation may refresh derived identity but must not silently promote governed state."""
    identity = {
        "manifest_records": 7,
        "source_tree_sha256": "a" * 64,
        "manifest_changed": True,
        "fingerprint_changed": True,
    }
    passed = {
        "name": "check",
        "command": ["example"],
        "returncode": 0,
        "status": "passed",
        "stdout": "",
        "stderr": "",
    }
    with (
        patch.object(
            preparation, "refresh_release_identity", return_value=identity
        ) as refresh,
        patch.object(preparation, "validate_release_identity") as validate,
        patch.object(preparation, "_run_check", return_value=passed) as run_check,
    ):
        result = preparation.prepare_validation_state(timeout=17)

    refresh.assert_called_once_with(preparation.ROOT)
    validate.assert_called_once_with(preparation.ROOT)
    assert run_check.call_args_list == [
        call("uv-lock-check", ["uv", "lock", "--check"], timeout=17),
        call(
            "continuous-security-assurance",
            [
                sys.executable,
                "scripts/security/verify_continuous_security_assurance.py",
            ],
            timeout=17,
        ),
    ]
    assert result["release_identity"] == identity
    not_auto_refreshed = cast(list[str], result["not_auto_refreshed"])
    assert (
        "docs/security/security_assurance_baseline_manifest.txt" in not_auto_refreshed
    )


def test_preparation_never_passes_security_baseline_promotion_flag() -> None:
    """Security baseline promotion stays behind the release profile's later gate."""
    with (
        patch.object(preparation, "refresh_release_identity", return_value={}),
        patch.object(preparation, "validate_release_identity"),
        patch.object(preparation, "_run_check") as run_check,
    ):
        run_check.return_value = {"status": "passed"}
        preparation.prepare_validation_state()

    security_command = run_check.call_args_list[1].args[1]
    assert "--promote-on-success" not in security_command
