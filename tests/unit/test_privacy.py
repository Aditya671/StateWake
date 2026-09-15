"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

import unittest
from datetime import UTC, datetime

from statewake.domain.events import EventEnvelope
from statewake.domain.privacy import (
    PrivacyPolicy,
    RedactionRule,
    Redactor,
    redact_events,
)


class PrivacyTests(unittest.TestCase):
    """Provide regression coverage for the PrivacyTests behavior."""

    def test_key_and_regex_redaction_are_deterministic(self) -> None:
        """Verify the `test_key_and_regex_redaction_are_deterministic` behavior
        and its expected invariants."""
        policy = PrivacyPolicy(
            policy_id="privacy-1",
            rules=(RedactionRule("email-rule", r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),),
        )
        result = Redactor(policy).redact_mapping(
            {
                "email": "alice@example.com",
                "message": "contact bob@example.com",
                "amount": 10,
            }
        )
        self.assertEqual(result.value["email"], "[REDACTED]")
        self.assertEqual(result.value["message"], "contact [REDACTED]")
        self.assertEqual(result.value["amount"], 10)
        self.assertEqual(result.findings, ("key:email", "rule:email-rule:message"))

    def test_nested_values_are_redacted_without_reordering_semantics(self) -> None:
        """Verify the `test_nested_values_are_redacted_without_reordering_semantics`
        behavior and its expected invariants."""
        policy = PrivacyPolicy(policy_id="privacy-1", redact_keys=("token",))
        result = Redactor(policy).redact_mapping(
            {"z": {"token": "abc"}, "a": [{"token": "def"}, "ok"]}
        )
        self.assertEqual(
            result.value,
            {"a": [{"token": "[REDACTED]"}, "ok"], "z": {"token": "[REDACTED]"}},
        )

    def test_event_redaction_preserves_identity_and_payload_reference(self) -> None:
        """Verify the `test_event_redaction_preserves_identity_and_payload_reference`
        behavior and its expected invariants."""
        event = EventEnvelope(
            "run-1",
            0,
            datetime.now(UTC),
            "tool.called",
            "runtime",
            name="lookup",
            payload_ref="sha256:abc",
            metadata={"authorization": "Bearer secret", "tool": "crm"},
        )
        redacted = Redactor(PrivacyPolicy(policy_id="privacy-1")).redact_event(event)
        self.assertEqual(redacted.run_id, event.run_id)
        self.assertEqual(redacted.sequence, event.sequence)
        self.assertEqual(redacted.payload_ref, event.payload_ref)
        self.assertEqual(redacted.metadata["authorization"], "[REDACTED]")

    def test_redact_events_preserves_event_sequence(self) -> None:
        """Verify the `test_redact_events_preserves_event_sequence` behavior
        and its expected invariants."""
        event = EventEnvelope(
            "run-1",
            0,
            datetime.now(UTC),
            "decision",
            "runtime",
            metadata={"token": "secret"},
        )
        redacted, findings = redact_events(
            [event], PrivacyPolicy(policy_id="privacy-1")
        )
        self.assertEqual(redacted[0].sequence, 0)
        self.assertEqual(findings, ("event:0",))


if __name__ == "__main__":
    unittest.main()
