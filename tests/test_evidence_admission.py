"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

import json
import tempfile
import unittest
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from statewake.adapters.content_store import ContentAddressedArtifactStore
from statewake.adapters.evidence_ingestion import (
    JsonEvidenceReceiptStore,
    LocalEvidenceIngestionAdapter,
)
from statewake.services.evidence_admission_service import admit_external_evidence


class ExternalEvidenceAdmissionTests(unittest.TestCase):
    """Provide regression coverage for the ExternalEvidenceAdmissionTests behavior."""

    def test_admits_receipt_against_real_artifact_and_reference(self):
        """
        Verify the `test_admits_receipt_against_real_artifact_and_reference`
        behavior and its expected invariants.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = LocalEvidenceIngestionAdapter(
                ContentAddressedArtifactStore(root / "cas"),
                JsonEvidenceReceiptStore(root / "receipts"),
            )
            receipt = adapter.ingest_bytes(
                b"external-output",
                producer_type="evaluation",
                producer_id="runner",
                source_ref="ci://42",
                source_event_id="event-42",
                run_id="run-42",
                captured_at=datetime(2026, 9, 11, tzinfo=UTC),
                metadata={"suite": "smoke"},
            )
            artifact = root / "artifact.json"
            artifact.write_bytes(b"external-output")
            receipt_path = root / "receipts" / f"{receipt.receipt_id}.json"
            admission = admit_external_evidence(
                receipt,
                artifact_path=artifact,
                receipt_path=receipt_path,
                expected_run_id="run-42",
            )
            self.assertEqual(admission.receipt_id, receipt.receipt_id)
            self.assertEqual(
                admission.evidence_reference.digest,
                sha256(b"external-output").hexdigest(),
            )
            assert admission.evidence_reference.receipt_ref is not None
            self.assertEqual(
                admission.evidence_reference.receipt_ref.identity, receipt.receipt_id
            )
            self.assertEqual(admission.from_dict(admission.to_dict()), admission)

    def test_admission_without_persisted_receipt_still_retains_receipt_binding(self):
        """
        Verify the
        `test_admission_without_persisted_receipt_still_retains_receipt_binding`
        behavior and its expected invariants.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = LocalEvidenceIngestionAdapter(
                ContentAddressedArtifactStore(root / "cas"),
                JsonEvidenceReceiptStore(root / "receipts"),
            )
            receipt = adapter.ingest_bytes(
                b"x",
                producer_type="ci",
                producer_id="runner",
                source_ref="ci://1",
                captured_at=datetime(2026, 9, 11, tzinfo=UTC),
                metadata={},
            )
            artifact = root / "artifact"
            artifact.write_bytes(b"x")
            admission = admit_external_evidence(receipt, artifact_path=artifact)
            self.assertIsNotNone(admission.evidence_reference.receipt_ref)
            assert admission.evidence_reference.receipt_ref is not None
            self.assertEqual(
                admission.evidence_reference.receipt_ref.identity, receipt.receipt_id
            )
            self.assertEqual(
                admission.evidence_reference.receipt_ref.digest, receipt.digest
            )

    def test_rejects_artifact_tampering(self):
        """
        Verify the `test_rejects_artifact_tampering` behavior
        and its expected invariants.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = LocalEvidenceIngestionAdapter(
                ContentAddressedArtifactStore(root / "cas"),
                JsonEvidenceReceiptStore(root / "receipts"),
            )
            receipt = adapter.ingest_bytes(
                b"trusted",
                producer_type="ci",
                producer_id="runner",
                source_ref="ci://1",
                captured_at=datetime(2026, 9, 11, tzinfo=UTC),
                metadata={},
            )
            artifact = root / "artifact"
            artifact.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "artifact digest"):
                admit_external_evidence(receipt, artifact_path=artifact)

    def test_rejects_wrong_run_and_producer(self):
        """
        Verify the `test_rejects_wrong_run_and_producer` behavior
        and its expected invariants.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = LocalEvidenceIngestionAdapter(
                ContentAddressedArtifactStore(root / "cas"),
                JsonEvidenceReceiptStore(root / "receipts"),
            )
            receipt = adapter.ingest_bytes(
                b"x",
                producer_type="ci",
                producer_id="runner",
                source_ref="ci://1",
                run_id="run-1",
                captured_at=datetime(2026, 9, 11, tzinfo=UTC),
                metadata={},
            )
            artifact = root / "artifact"
            artifact.write_bytes(b"x")
            with self.assertRaisesRegex(ValueError, "run_id"):
                admit_external_evidence(
                    receipt, artifact_path=artifact, expected_run_id="run-2"
                )
            with self.assertRaisesRegex(ValueError, "producer_id"):
                admit_external_evidence(
                    receipt, artifact_path=artifact, expected_producer_id="other"
                )

    def test_rejects_persisted_receipt_mismatch(self):
        """
        Verify the `test_rejects_persisted_receipt_mismatch` behavior
        and its expected invariants.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = LocalEvidenceIngestionAdapter(
                ContentAddressedArtifactStore(root / "cas"),
                JsonEvidenceReceiptStore(root / "receipts"),
            )
            receipt = adapter.ingest_bytes(
                b"x",
                producer_type="ci",
                producer_id="runner",
                source_ref="ci://1",
                captured_at=datetime(2026, 9, 11, tzinfo=UTC),
                metadata={},
            )
            artifact = root / "artifact"
            artifact.write_bytes(b"x")
            path = root / "receipt.json"
            payload = receipt.to_dict()
            payload["producer_id"] = "attacker"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises((ValueError, KeyError)):
                admit_external_evidence(
                    receipt, artifact_path=artifact, receipt_path=path
                )


if __name__ == "__main__":
    unittest.main()
