"""Regression coverage for StateWake adversarial validation probes."""

from __future__ import annotations

from scripts.common.validation_types import ValidationReport
from scripts.testing.run_chaos_validation import run


def test_chaos_validation_matrix_passes() -> None:
    """Require every deterministic adversarial probe to pass."""
    result: ValidationReport = run()
    assert result["passed"] is True
    assert result["probe_count"] == 8  # type: ignore
    assert all(item["passed"] for item in result["results"])
