"""JSON renderer for StateWake human verification reports."""

from __future__ import annotations

import json

from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.reports.validation import validate_report


def render_json_report(report: ReliabilityVerificationReport) -> str:
    """Render a deterministic JSON report including its digest."""
    validate_report(report)
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


__all__ = ["render_json_report"]
