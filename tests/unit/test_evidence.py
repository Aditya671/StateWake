"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

import tempfile
import unittest
from pathlib import Path

from statewake.adapters.content_store import ContentAddressedArtifactStore
from statewake.domain.evidence import EvidenceItem, EvidenceManifest


class EvidenceTests(unittest.TestCase):
    """Provide regression coverage for the EvidenceTests behavior."""

    def test_manifest_round_trip_and_unique_ids(self):
        """Verify the `test_manifest_round_trip_and_unique_ids` behavior and
        its expected invariants."""
        item = EvidenceItem("e1", "crm", digest="abc")
        manifest = EvidenceManifest("m1", "run-1", (item,))
        self.assertEqual(EvidenceManifest.from_dict(manifest.to_dict()), manifest)
        with self.assertRaisesRegex(ValueError, "unique"):
            EvidenceManifest("m1", "run-1", (item, item))

    def test_evidence_requires_reference(self):
        """Verify the `test_evidence_requires_reference` behavior and
        its expected invariants."""
        with self.assertRaisesRegex(ValueError, "digest or content_ref"):
            EvidenceItem("e1", "crm")

    def test_content_store_is_content_addressed_and_verifies_integrity(self):
        """Verify the `test_content_store_is_content_addressed_and_verifies_integrity`
        behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as d:
            store = ContentAddressedArtifactStore(Path(d))
            content = b"evidence"
            digest = store.put(content)
            self.assertEqual(store.get(digest), content)
            self.assertTrue(store.exists(digest))
            self.assertEqual(store.put(content), digest)
            path = Path(d) / digest[:2] / digest[2:]
            path.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "integrity"):
                store.get(digest)
