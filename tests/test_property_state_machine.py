"""Regression coverage for deterministic property and state-machine checks."""

from scripts.testing.property_state_machine import run


def test_property_and_state_machine_campaign() -> None:
    """Verify generated properties and state-machine invariants hold."""
    report = run(seed=20260913, cases=40, steps=20)
    assert report["passed"] is True
    assert report["property_count"] == 5  # type: ignore
    assert all(result["passed"] for result in report["results"])
