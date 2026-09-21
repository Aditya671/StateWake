"""Regression coverage for Tier 10 bounded assurance operations."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from statewake.domain.assurance_operations import (
    AssuranceDecisionInput,
    SecurityDecision,
    create_assurance_exception,
    evaluate_assurance_decision,
)

NOW = datetime(2026, 9, 16, 4, 0, tzinfo=UTC)


class TestAssuranceOperations(unittest.TestCase):
    """Verify deterministic security-assurance decisions and exception semantics."""

    def _evaluate(
        self,
        *,
        reliability_state: str = "reliable",
        verification_status: str = "verified",
        trust_status: str = "trusted",
        recovery_required: bool = False,
    ):
        return evaluate_assurance_decision(
            AssuranceDecisionInput(
                subject_id="agent-1",
                reliability_state=reliability_state,
                verification_status=verification_status,
                trust_status=trust_status,
                evidence_references=("chain:abc", "transition:def"),
                verification_results=("chain_verified", "transition_verified"),
                recovery_required=recovery_required,
            ),
            generated_at=NOW,
        )

    def test_verified_reliable_allows(self):
        decision = self._evaluate()
        self.assertEqual(decision.decision, SecurityDecision.ALLOW)
        self.assertTrue(decision.system_state_unchanged)
        self.assertEqual(decision.generated_at, NOW.isoformat())
        self.assertIn("policy-rule:verified-reliability-state", decision.rationale)

    def test_limitations_and_unavailability_require_bounded_handling(self):
        limited = self._evaluate(verification_status="verified_with_limitations")
        self.assertEqual(limited.decision, SecurityDecision.ALLOW_WITH_LIMITATIONS)

        unavailable = self._evaluate(verification_status="trust_anchor_unavailable")
        self.assertEqual(unavailable.decision, SecurityDecision.REQUIRE_REVERIFICATION)

    def test_tampering_quarantines_and_invalid_evidence_rejects(self):
        tampered = self._evaluate(verification_status="tampered")
        self.assertEqual(tampered.decision, SecurityDecision.QUARANTINE)

        invalid = self._evaluate(verification_status="invalid")
        self.assertEqual(invalid.decision, SecurityDecision.REJECT)

    def test_unreliable_and_recovery_states_are_deterministic(self):
        unreliable = self._evaluate(reliability_state="unreliable")
        self.assertEqual(unreliable.decision, SecurityDecision.REJECT)

        recovery = self._evaluate(recovery_required=True)
        self.assertEqual(recovery.decision, SecurityDecision.RECOVERY_REQUIRED)

    def test_revoked_trust_is_not_downgraded_to_review(self):
        decision = self._evaluate(trust_status="revoked")
        self.assertEqual(decision.decision, SecurityDecision.REVOKE_TRUST)

    def test_decision_digest_is_stable_and_bound_to_evidence(self):
        first = self._evaluate()
        second = self._evaluate()
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(first.evidence_references, ("chain:abc", "transition:def"))
        self.assertEqual(first.computed_digest(), first.digest)

    def test_human_exception_preserves_system_state(self):
        decision = self._evaluate(reliability_state="degraded")
        exception = create_assurance_exception(
            decision,
            exception_id="exc-1",
            reason_operation_continues="approved operational exception",
            authorized_by="security-owner",
            expires_at=NOW + timedelta(hours=4),
            compensating_control="manual verification",
            reverification_required="before expiry",
            created_at=NOW,
        )
        self.assertTrue(exception.system_state_preserved)
        self.assertEqual(exception.subject_id, "agent-1")
        self.assertEqual(exception.evidence_references, decision.evidence_references)
        self.assertEqual(exception.computed_digest(), exception.digest)

    def test_exception_cannot_override_clear_or_reject_decisions(self):
        allowed = self._evaluate()
        with self.assertRaises(ValueError):
            create_assurance_exception(
                allowed,
                exception_id="exc-2",
                reason_operation_continues="not needed",
                authorized_by="security-owner",
                expires_at=NOW + timedelta(hours=1),
                compensating_control="none",
                reverification_required="none",
                created_at=NOW,
            )

        rejected = self._evaluate(verification_status="invalid")
        with self.assertRaises(ValueError):
            create_assurance_exception(
                rejected,
                exception_id="exc-3",
                reason_operation_continues="should not continue",
                authorized_by="security-owner",
                expires_at=NOW + timedelta(hours=1),
                compensating_control="none",
                reverification_required="required",
                created_at=NOW,
            )


if __name__ == "__main__":
    unittest.main()
