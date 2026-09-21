"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from statewake.adapters.content_store import ContentAddressedArtifactStore
from statewake.adapters.evidence_ingestion import (
    JsonEvidenceReceiptStore,
    LocalEvidenceIngestionAdapter,
)
from statewake.domain.evidence_receipt import ExternalEvidenceReceipt
from statewake.services.evidence_ingestion_service import (
    ingest_evidence_file,
    load_evidence_receipt,
    verify_evidence_receipt,
)


class ExternalEvidenceIngestionTests(unittest.TestCase):
    """Provide regression coverage for the ExternalEvidenceIngestionTests behavior."""

    def _adapter(self, root: Path) -> LocalEvidenceIngestionAdapter:
        """Verify the `_adapter` behavior and its expected invariants."""
        return LocalEvidenceIngestionAdapter(
            ContentAddressedArtifactStore(root / "artifacts"),
            JsonEvidenceReceiptStore(root / "receipts"),
        )

    def _kwargs(self) -> dict[str, object]:
        """Verify the `_kwargs` behavior and its expected invariants."""
        return {
            "producer_type": "evaluation",
            "producer_id": "eval-runner",
            "producer_version": "2.1",
            "source_ref": "ci://build/42/evaluation.json",
            "source_event_id": "event-42",
            "run_id": "run-42",
            "captured_at": datetime(2026, 9, 11, 12, 0, tzinfo=UTC),
            "metadata": {"environment": "ci", "suite": "smoke"},
        }

    def test_ingest_is_content_addressed_and_referential(self):
        """
        Verify the `test_ingest_is_content_addressed_and_referential` behavior
        and its expected invariants.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = self._adapter(root).ingest_bytes(
                b"result: pass\n",
                **self._kwargs(),  # type: ignore
            )
            self.assertEqual(
                receipt.artifact_digest, sha256(b"result: pass\n").hexdigest()
            )
            self.assertEqual(receipt.artifact_size, 13)
            self.assertEqual(receipt.artifact_reference().identity, receipt.receipt_id)
            self.assertIsNone(receipt.artifact_reference().source)
            self.assertTrue(
                (
                    root
                    / "artifacts"
                    / receipt.artifact_digest[:2]
                    / receipt.artifact_digest[2:]
                ).is_file()
            )
            self.assertTrue(
                (root / "receipts" / f"{receipt.receipt_id}.json").is_file()
            )

    def test_receipt_identity_and_digest_are_deterministic(self):
        """
        Verify the `test_receipt_identity_and_digest_are_deterministic` behavior
        and its expected invariants.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self._adapter(root).ingest_bytes(b"same", **self._kwargs())  # type: ignore
            second = self._adapter(root).ingest_bytes(b"same", **self._kwargs())  # type: ignore
            self.assertEqual(first, second)
            self.assertEqual(first.receipt_id, first.computed_receipt_id())
            self.assertEqual(first.digest, first.computed_digest())

    def test_concurrent_duplicate_ingestion_is_idempotent(self):
        """
        Verify the `test_concurrent_duplicate_ingestion_is_idempotent`
        behavior and its expected invariants.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = self._adapter(root)
            kwargs = self._kwargs()
            with ThreadPoolExecutor(max_workers=8) as pool:
                receipts = list(
                    pool.map(
                        lambda _: adapter.ingest_bytes(b"same", **kwargs),  # type: ignore
                        range(16),  # type: ignore
                    )
                )
            self.assertEqual(len({receipt.receipt_id for receipt in receipts}), 1)
            self.assertEqual(len(list((root / "receipts").glob("*.json"))), 1)
            adapter.verify(receipts[0])

    def test_source_event_conflict_is_rejected(self):
        """
        Verify the `test_source_event_conflict_is_rejected` behavior
        and its expected invariants.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = self._adapter(root)
            adapter.ingest_bytes(b"original", **self._kwargs())  # type: ignore
            with self.assertRaisesRegex(ValueError, "source_event_id conflict"):
                adapter.ingest_bytes(b"changed", **self._kwargs())  # type: ignore

    def test_content_store_put_rejects_existing_corruption(self):
        """
        Verify the `test_content_store_put_rejects_existing_corruption` behavior
        and its expected invariants.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ContentAddressedArtifactStore(root / "artifacts")
            digest = store.put(b"original")
            target = root / "artifacts" / digest[:2] / digest[2:]
            target.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "Artifact integrity failure"):
                store.put(b"original")

    def test_tampered_artifact_is_detected(self):
        """
        Verify the `test_tampered_artifact_is_detected` behavior
        and its expected invariants.
        """
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = self._adapter(root)
            receipt = adapter.ingest_bytes(b"trusted", **self._kwargs())  # type: ignore
            artifact = (
                root
                / "artifacts"
                / receipt.artifact_digest[:2]
                / receipt.artifact_digest[2:]
            )
            artifact.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "Artifact integrity failure"):
                adapter.verify(receipt)

    def test_tampered_receipt_is_detected(self):
        """Verify the `test_tampered_receipt_is_detected` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = self._adapter(root)
            receipt = adapter.ingest_bytes(b"trusted", **self._kwargs())  # type: ignore
            receipt_path = root / "receipts" / f"{receipt.receipt_id}.json"
            payload = json.loads(receipt_path.read_text(encoding="utf-8"))
            payload["producer_id"] = "attacker"
            receipt_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest|receipt_id"):
                adapter.verify(receipt)

    def test_invalid_naive_capture_time_is_rejected(self):
        """Verify the `test_invalid_naive_capture_time_is_rejected` behavior and its expected invariants."""
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            ExternalEvidenceReceipt(
                producer_type="ci",
                producer_id="runner",
                artifact_digest="a" * 64,
                artifact_size=1,
                captured_at=datetime.fromisoformat("2026-09-11T00:00:00"),
                source_ref="ci://1",
            )

    def test_service_roundtrip(self):
        """Verify the `test_service_roundtrip` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "result.json"
            artifact.write_text('{"passed":true}\n', encoding="utf-8")
            receipt = ingest_evidence_file(
                artifact,
                artifact_store_root=root / "cas",
                receipt_store_root=root / "receipt-store",
                producer_type="ci",
                producer_id="github-actions",
                source_event_id="job-17",
                captured_at=datetime(2026, 9, 11, 12, 0, tzinfo=UTC),
            )
            receipt_path = root / "receipt-store" / f"{receipt.receipt_id}.json"
            loaded = load_evidence_receipt(receipt_path)
            self.assertEqual(loaded, receipt)
            verify_evidence_receipt(
                receipt,
                artifact_store_root=root / "cas",
                receipt_store_root=root / "receipt-store",
            )

    def test_receipt_adapts_to_existing_evidence_manifest_item(self):
        """Verify the `test_receipt_adapts_to_existing_evidence_manifest_item` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = self._adapter(root).ingest_bytes(b"manifest", **self._kwargs())  # type: ignore
            item = receipt.to_evidence_item()
            self.assertEqual(item.evidence_id, receipt.receipt_id)
            self.assertEqual(item.digest, receipt.artifact_digest)
            self.assertEqual(item.content_ref, f"cas:{receipt.artifact_digest}")
            self.assertEqual(item.metadata["producer_id"], receipt.producer_id)

    def test_receipt_adaptation_preserves_external_metadata(self):
        """Verify the `test_receipt_adaptation_preserves_external_metadata` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            receipt = self._adapter(root).ingest_bytes(
                b"manifest",
                **{**self._kwargs(), "metadata": {"suite": "smoke", "attempt": "2"}},  # type: ignore
            )
            item = receipt.to_evidence_item()
            self.assertEqual(item.metadata["suite"], "smoke")
            self.assertEqual(item.metadata["attempt"], "2")
            self.assertEqual(item.metadata["receipt_id"], receipt.receipt_id)

    def test_receipt_can_link_existing_provenance(self):
        """Verify the `test_receipt_can_link_existing_provenance` behavior and its expected invariants."""
        from statewake.domain.reliability_evidence import EvidenceReference

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            provenance = EvidenceReference("provenance", "prov-42", "c" * 64)
            receipt = self._adapter(root).ingest_bytes(
                b"data",
                **{**self._kwargs(), "provenance_ref": provenance},  # type: ignore
            )
            self.assertEqual(receipt.provenance_ref, provenance)
            self.assertEqual(
                receipt.to_evidence_item().metadata["receipt_id"], receipt.receipt_id
            )


if __name__ == "__main__":
    unittest.main()


def test_ingest_bytes_requires_source_ref() -> None:
    """Reject a direct bytes-ingestion call that supplies no source reference."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        adapter = LocalEvidenceIngestionAdapter(
            ContentAddressedArtifactStore(root / "artifacts"),
            JsonEvidenceReceiptStore(root / "receipts"),
        )
        kwargs = {
            "producer_type": "test",
            "producer_id": "producer-1",
            "captured_at": datetime(2026, 9, 13, tzinfo=UTC),
            "source_ref": None,
        }
        with pytest.raises(ValueError, match="source_ref"):
            adapter.ingest_bytes(b"payload", **kwargs)  # type: ignore[arg-type]
