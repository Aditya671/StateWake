"""Focused tests for SDLC coordinator diagnostics and timeout policy."""

from __future__ import annotations

import scripts.release.run_sdlc_validation as sdlc


def test_long_running_gates_receive_an_extended_timeout() -> None:
    """Known regression/adversarial gates receive the documented extended budget."""
    assert sdlc._gate_timeout("unit-and-integration-tests", 100) == 300
    assert sdlc._gate_timeout("version-identity", 100) == 100
    assert sdlc._gate_timeout("unit-and-integration-tests", 0) is None


def test_failure_output_prefers_pytest_failure_section() -> None:
    """Failure evidence should expose assertions instead of only progress tails."""
    noisy_progress = "progress\n" * 4000
    failure = (
        "=================================== FAILURES ===================================\n"
        "________________ failing_test _________________\n"
        "E   AssertionError: expected clear failure evidence\n"
    )
    excerpt = sdlc._output_excerpt(noisy_progress + failure, limit=400)
    assert excerpt.startswith("=================================== FAILURES")
    assert "expected clear failure evidence" in excerpt
    assert "progress" not in excerpt


def test_validation_profiles_do_not_mutate_candidate_state() -> None:
    """SDLC verification must not sync dependencies or promote/refresh maintained state."""
    forbidden = {
        "uv sync",
        "refresh_release_identity.py",
        "promote_security_assurance_baseline.py",
        "--promote-on-success",
    }
    for profile in ("check", "release"):
        rendered = [" ".join(command) for _, command in sdlc.command_plan(profile)]
        combined = "\n".join(rendered)
        assert all(token not in combined for token in forbidden)
        assert any("uv lock --check" in command for command in rendered)
