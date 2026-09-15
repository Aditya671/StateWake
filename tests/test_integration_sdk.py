"""Tests for the framework-neutral StateWake integration SDK."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from statewake import (
    AgentEvidenceAdapter,
    AgentRunEvidence,
    BatchEvidenceAdapter,
    BatchRun,
    DatabaseChange,
    DatabaseEvidenceAdapter,
    IntegrationContext,
    InvalidEvidenceError,
    QueueEvidenceAdapter,
    QueueMessage,
    StateWakeClient,
    WebhookEvent,
    WebhookEvidenceAdapter,
)

NOW = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)


def _client(root: Path) -> StateWakeClient:
    return StateWakeClient.for_root(
        IntegrationContext("producer-1", run_id="run-1"), root=root
    )


def test_python_client_ingests_and_verifies_bytes(tmp_path: Path) -> None:
    client = _client(tmp_path)
    receipt = client.ingest_bytes(
        b"hello",
        producer_type="application",
        source_ref="event-1",
        source_event_id="event-1",
        captured_at=NOW,
    )
    client.verify_receipt(receipt)
    assert receipt.producer_id == "producer-1"
    assert receipt.source_event_id == "event-1"


def test_webhook_adapter_preserves_delivery_metadata(tmp_path: Path) -> None:
    receipt = WebhookEvidenceAdapter(_client(tmp_path)).ingest(
        WebhookEvent("request-1", b"{}", "application/json", "sig", 2),
        captured_at=NOW,
    )
    assert receipt.producer_type == "webhook"
    assert receipt.metadata["delivery_attempt"] == "2"
    assert receipt.metadata["signature"] == "sig"


def test_queue_adapter_preserves_message_identity(tmp_path: Path) -> None:
    receipt = QueueEvidenceAdapter(_client(tmp_path)).ingest(
        QueueMessage("message-1", b"payload", partition="3", sequence_number=7),
        captured_at=NOW,
    )
    assert receipt.source_event_id == "message-1"
    assert receipt.metadata["partition"] == "3"
    assert receipt.metadata["sequence_number"] == "7"


def test_database_adapter_captures_structured_observation(tmp_path: Path) -> None:
    receipt = DatabaseEvidenceAdapter(_client(tmp_path)).ingest(
        DatabaseChange("tx-1", "order-1", {"status": "paid"}, {"status": "paid"}, NOW),
        captured_at=NOW,
    )
    assert receipt.producer_type == "database"
    assert receipt.artifact_size > 0


def test_batch_adapter_captures_pipeline_identity(tmp_path: Path) -> None:
    receipt = BatchEvidenceAdapter(_client(tmp_path)).ingest(
        BatchRun("job-1", "input-1", "output-1", "v2", 42),
        captured_at=NOW,
    )
    assert receipt.source_event_id == "job-1"


def test_agent_adapter_captures_references_without_payloads(tmp_path: Path) -> None:
    receipt = AgentEvidenceAdapter(_client(tmp_path)).ingest(
        AgentRunEvidence("agent-1", "model@1", prompt_ref="sha256:prompt"),
        captured_at=NOW,
    )
    assert receipt.producer_type == "agent-run"
    assert receipt.source_event_id == "agent-1"


def test_invalid_webhook_metadata_fails_before_persistence(tmp_path: Path) -> None:
    with pytest.raises(InvalidEvidenceError, match="content_type"):
        WebhookEvidenceAdapter(_client(tmp_path)).ingest(
            WebhookEvent("request-1", b"{}", "", None),
            captured_at=NOW,
        )
