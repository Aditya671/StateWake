"""Regression tests for the StateWake SDLC verification coordinator."""

from __future__ import annotations

import scripts.release.run_sdlc_validation as sdlc
from config.project_paths import PROJECT_ROOT

ROOT = PROJECT_ROOT


def test_strict_typecheck_installs_optional_integration_types() -> None:
    """Type checking must resolve the optional SDK APIs checked by mypy."""
    commands = dict(sdlc.command_plan("check"))
    assert commands["strict-typecheck"] == [
        "uv",
        "run",
        "--extra",
        "integrations",
        "mypy",
    ]


def test_check_profile_has_required_ordered_gates() -> None:
    """Require the inexpensive SDLC profile to preserve the intended gate order."""
    names = [name for name, _ in sdlc.command_plan("check")]
    assert names == [
        "repository-structure",
        "version-identity",
        "source-quality",
        "ruff-check",
        "ruff-format",
        "strict-typecheck",
        "source-compilation",
        "unit-and-integration-tests",
        "product-experience",
        "cli-surface",
    ]


def test_release_profile_extends_check_with_hardening_and_release_gates() -> None:
    """Require release validation to extend, rather than replace, the check profile."""
    check = [name for name, _ in sdlc.command_plan("check")]
    release = [name for name, _ in sdlc.command_plan("release")]
    assert release[: len(check)] == check
    assert "failure-lab" in release
    assert "public-trial-regressions" in release
    assert release.index("public-trial-regressions") < release.index(
        "release-candidate"
    )
    assert "release-candidate" in release
