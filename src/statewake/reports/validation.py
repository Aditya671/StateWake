"""Validation helpers for human-readable StateWake reports."""

from __future__ import annotations

from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)


def validate_report(report: ReliabilityVerificationReport) -> None:
    """Validate cross-section report invariants."""
    # Construction already performs most validation. This helper gives callers a
    # stable Phase 3 validation hook without duplicating model logic.
    if set(report.evidence_missing) & set(report.evidence_included):
        raise ValueError("missing evidence cannot also be included evidence.")
    if report.decision == "accept" and report.approval_status == "approved":
        # Accept may be the StateWake profile decision, but approval must remain
        # a separately scoped human decision.
        if not report.human_decisions_required:
            raise ValueError("accepted approved reports must carry approval scope.")


__all__ = ["validate_report"]
