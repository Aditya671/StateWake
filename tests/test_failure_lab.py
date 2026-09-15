"""Regression coverage for the canonical StateWake failure laboratory."""

from scripts.common.validation_types import ValidationReport
from scripts.testing.failure_lab import run


def test_failure_lab_campaign_passes() -> None:
    """Require every catalogued attack to fail closed across supported platforms."""
    report: ValidationReport = run()
    assert report["passed"] is True
    assert report["attack_count"] == 10
    assert all(item["passed"] for item in report["results"])
