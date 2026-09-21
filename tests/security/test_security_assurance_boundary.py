"""Regression tests for the Tier 4 security-assurance evidence boundary."""

from __future__ import annotations

from config.project_paths import PROJECT_ROOT
from scripts.security.verify_security_assurance_boundary import (
    verify_security_assurance_boundary,
)


def test_security_assurance_evidence_is_internally_consistent() -> None:
    """Security claims, threat coverage, and executable references remain aligned."""
    assert verify_security_assurance_boundary(PROJECT_ROOT) == []


def test_security_assurance_is_not_a_release() -> None:
    """Tier 4 assurance evidence must not alter release identity or status."""
    version_source = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assurance = (
        PROJECT_ROOT / "docs" / "security" / "TIER4_SECURITY_ASSURANCE.md"
    ).read_text(encoding="utf-8")

    assert 'version = "0.3.0"' in version_source
    assert "not a release approval" in assurance
