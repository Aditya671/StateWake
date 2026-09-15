import unittest
from datetime import UTC, datetime, timedelta

from statewake.adapters.retention import InMemoryEvidenceRetentionAdapter
from statewake.domain.operational_hooks import ReliabilityFailureEvent
from statewake.domain.retention import EvidenceRetentionRequirement


class TestRetentionAndHooks(unittest.TestCase):
    def test_legal_hold_blocks_delete_after_expiry(self):
        now = datetime.now(UTC)
        store = InMemoryEvidenceRetentionAdapter()
        store.require_retention(
            EvidenceRetentionRequirement("a", now - timedelta(days=1), legal_hold=True)
        )
        self.assertFalse(store.can_delete("a", now=now))
        store.release_retention("a")
        self.assertTrue(store.is_held("a"))

    def test_expired_nonheld_requirement_can_delete(self):
        now = datetime.now(UTC)
        store = InMemoryEvidenceRetentionAdapter()
        store.require_retention(
            EvidenceRetentionRequirement("a", now - timedelta(days=1))
        )
        self.assertTrue(store.can_delete("a", now=now))

    def test_failure_event_is_portable(self):
        event = ReliabilityFailureEvent.now(
            "verification_failure",
            "verify_chain",
            "tampered artifact",
            subject_id="release-1",
        )
        payload = event.to_dict()
        self.assertEqual(payload["event_type"], "verification_failure")
        self.assertEqual(payload["subject_id"], "release-1")


if __name__ == "__main__":
    unittest.main()
