"""Report model aliases for StateWake human verification reports.

Phase 3 extends the existing :class:`ReliabilityVerificationReport` contract
instead of introducing a duplicate report authority.
"""

from __future__ import annotations

from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)

HumanVerificationReport = ReliabilityVerificationReport
EngineeringVerificationReport = ReliabilityVerificationReport
BusinessDecisionReport = ReliabilityVerificationReport
AIRiskReport = ReliabilityVerificationReport
ReleaseEvidenceReport = ReliabilityVerificationReport
IncidentRecoveryReport = ReliabilityVerificationReport

__all__ = [
    "AIRiskReport",
    "BusinessDecisionReport",
    "EngineeringVerificationReport",
    "HumanVerificationReport",
    "IncidentRecoveryReport",
    "ReleaseEvidenceReport",
    "ReliabilityVerificationReport",
]
