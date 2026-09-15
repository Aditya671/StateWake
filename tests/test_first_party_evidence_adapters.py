import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from statewake.adapters.content_store import ContentAddressedArtifactStore
from statewake.adapters.evidence_ingestion import (
    JsonEvidenceReceiptStore,
    LocalEvidenceIngestionAdapter,
)
from statewake.adapters.first_party_evidence import (
    AgentRunLogAdapter,
    CICDArtifactAdapter,
    EvaluationOutputAdapter,
    EvidenceAdapterContext,
    IncidentRecoveryRecordAdapter,
    OpenTelemetryTraceAdapter,
)


class TestFirstPartyEvidenceAdapters(unittest.TestCase):
    def _ingestion(self, root: Path) -> LocalEvidenceIngestionAdapter:
        return LocalEvidenceIngestionAdapter(
            ContentAddressedArtifactStore(root / "artifacts"),
            JsonEvidenceReceiptStore(root / "receipts"),
        )

    def test_ci_adapter_is_thin_and_canonical(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "build.json"
            artifact.write_text('{"build":"42"}\n', encoding="utf-8")
            receipt = CICDArtifactAdapter(
                self._ingestion(root),
                EvidenceAdapterContext(
                    "github-actions",
                    producer_version="1",
                    source_event_id="job-42",
                    run_id="run-42",
                    metadata={"branch": "main"},
                ),
            ).ingest(
                artifact,
                captured_at=datetime(2026, 9, 11, tzinfo=UTC),
                source_ref="ci://build/42/build.json",
            )
            self.assertEqual(receipt.producer_type, "ci-cd")
            self.assertEqual(receipt.producer_id, "github-actions")
            self.assertEqual(receipt.source_ref, "ci://build/42/build.json")
            self.assertEqual(receipt.run_id, "run-42")
            self.assertEqual(receipt.metadata["branch"], "main")

    def test_all_first_party_sources_map_to_distinct_producer_types(self):
        self.assertEqual(OpenTelemetryTraceAdapter.producer_type, "opentelemetry")
        self.assertEqual(AgentRunLogAdapter.producer_type, "agent-run")
        self.assertEqual(EvaluationOutputAdapter.producer_type, "evaluation")
        self.assertEqual(
            IncidentRecoveryRecordAdapter.producer_type, "incident-recovery"
        )

    def test_adapter_rejects_naive_capture_time(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "result.json"
            artifact.write_text("{}", encoding="utf-8")
            adapter = EvaluationOutputAdapter(
                self._ingestion(root), EvidenceAdapterContext("eval")
            )
            with self.assertRaisesRegex(ValueError, "timezone-aware"):
                adapter.ingest(
                    artifact, captured_at=datetime.fromisoformat("2026-09-11T00:00:00")
                )

    def test_missing_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            adapter = AgentRunLogAdapter(
                self._ingestion(root), EvidenceAdapterContext("agent")
            )
            with self.assertRaises(FileNotFoundError):
                adapter.ingest(root / "missing.log")


if __name__ == "__main__":
    unittest.main()
