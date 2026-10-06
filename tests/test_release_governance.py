"""Behavioral release-governance regression tests."""

from __future__ import annotations

import scripts.release.run_sdlc_validation as sdlc


def test_release_profile_preserves_human_publication_boundary() -> None:
    """Release validation must finish with verification, never publication."""
    names = [name for name, _ in sdlc.command_plan("release")]
    assert "release-candidate" in names
    assert names.index("continuous-security-assurance") < names.index(
        "final-release-identity-refresh"
    )
    assert names.index("final-release-identity-refresh") < names.index(
        "release-candidate"
    )


def test_release_identity_is_stabilized_before_it_is_verified() -> None:
    """Every SDLC profile must prepare current identity before checking it."""
    for profile in ("check", "release"):
        names = [name for name, _ in sdlc.command_plan(profile)]
        assert names.index("validation-state-stabilization") < names.index(
            "release-identity-verify"
        )
