"""Regression entry point for the extreme failure-injection campaign."""

from __future__ import annotations

from scripts.testing.run_extreme_validation import run


def test_extreme_validation_matrix_passes() -> None:
    """Require every extreme validation probe to pass."""
    report = run()
    assert report["passed"] is True
    assert report.get("probe_count") == 8
