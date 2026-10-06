"""Regression tests for the Tier 4 security-assurance boundary inventory."""

from __future__ import annotations

from scripts.common.project_paths import PROJECT_ROOT
from scripts.security.verify_security_assurance_boundary import (
    REQUIRED_SECURITY_DOCS,
    REQUIRED_SECURITY_SCRIPTS,
    REQUIRED_SECURITY_TESTS,
    verify_security_assurance_boundary,
)


def test_security_assurance_boundary_is_structurally_intact() -> None:
    """Maintained security documents, tests, and verifier scripts must exist and parse."""
    assert verify_security_assurance_boundary(PROJECT_ROOT) == []


def test_security_assurance_inventory_points_only_to_maintained_paths() -> None:
    """The executable inventory must resolve to real repository paths, not prose markers."""
    for relative in (
        *REQUIRED_SECURITY_DOCS,
        *REQUIRED_SECURITY_TESTS,
        *REQUIRED_SECURITY_SCRIPTS,
    ):
        assert (PROJECT_ROOT / relative).is_file(), relative
