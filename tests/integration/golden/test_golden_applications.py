"""Executable regression coverage for the three golden applications."""

from __future__ import annotations

from docs.examples.golden.runtime import (
    run_enterprise_ai,
    run_municipal,
    run_payment,
)


def test_payment_golden_application() -> None:
    """Require the payment application to verify its complete lifecycle."""
    result = run_payment()
    assert result.chain_verified
    assert result.outcome_verified
    assert result.proof_bundle_verified
    assert result.tamper_rejected
    assert "different bytes" in result.injected_failure


def test_enterprise_ai_golden_application() -> None:
    """Require the enterprise AI application to verify its evidence lifecycle."""
    result = run_enterprise_ai()
    assert result.chain_verified
    assert result.outcome_verified
    assert result.proof_bundle_verified
    assert result.tamper_rejected


def test_municipal_golden_application() -> None:
    """Require policy change to produce an explicit review outcome."""
    result = run_municipal()
    assert result.chain_verified
    assert result.outcome_verified
    assert result.proof_bundle_verified
    assert result.tamper_rejected
    assert "degraded/review" in result.injected_failure
