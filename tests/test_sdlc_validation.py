"""Regression tests for the StateWake SDLC verification coordinator."""

from __future__ import annotations

import scripts.release.run_sdlc_validation as sdlc


def test_typecheck_uses_the_prepared_locked_environment() -> None:
    """SDLC validation must not trigger dependency resolution during type checking."""
    commands = dict(sdlc.command_plan("check"))
    assert commands["strict-typecheck"] == ["uv", "run", "--no-sync", "mypy"]


def test_check_profile_stabilizes_identity_before_verification() -> None:
    """Safe generated state is stabilized before release consistency assertions."""
    names = [name for name, _ in sdlc.command_plan("check")]
    assert names[:2] == ["validation-state-stabilization", "release-identity-verify"]
    assert "unit-and-integration-tests" in names
    assert "product-experience" in names
    assert "cli-surface" in names
    assert names[-1] == "post-check-release-identity-verify"


def test_release_profile_promotes_security_before_final_identity() -> None:
    """Promoted security evidence must be included in the final release identity."""
    release = [name for name, _ in sdlc.command_plan("release")]
    assert "continuous-security-assurance" in release
    assert release.index("continuous-security-assurance") < release.index(
        "final-release-identity-refresh"
    )
    assert release.index("final-release-identity-refresh") < release.index(
        "final-release-identity-verify"
    )
    assert release.index("final-release-identity-verify") < release.index(
        "release-candidate"
    )


def test_long_running_gates_receive_an_extended_timeout() -> None:
    """Known regression/adversarial gates are not constrained by the short base budget."""
    assert sdlc._gate_timeout("unit-and-integration-tests", 100) == 300
    assert sdlc._gate_timeout("version-identity", 100) == 100
    assert sdlc._gate_timeout("unit-and-integration-tests", 0) is None
