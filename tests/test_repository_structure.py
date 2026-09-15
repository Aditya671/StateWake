"""Regression tests for the organized StateWake repository boundary."""

from __future__ import annotations

import scripts.release.verify_repository_structure as verifier
from config.project_paths import PROJECT_ROOT

ROOT = PROJECT_ROOT


def test_repository_structure_is_current() -> None:
    """Require the repository to use the canonical categorized layout."""
    assert verifier.main() == 0
