"""Thin first-party receipt adapters for common evidence-producing boundaries.

These adapters intentionally do not interpret, evaluate, or monitor producer output.
They capture an existing artifact and turn it into the canonical external-evidence
receipt used by StateWake's V1 lifecycle.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from ..adapters.evidence_ingestion import LocalEvidenceIngestionAdapter
from ..domain.evidence_receipt import ExternalEvidenceReceipt


def _empty_metadata() -> dict[str, str]:
    """Create an empty string-to-string metadata mapping."""
    return {}


@dataclass(frozen=True, slots=True)
class EvidenceAdapterContext:
    """Producer identity shared by thin first-party evidence adapters."""

    producer_id: str
    producer_version: str | None = None
    source_event_id: str | None = None
    run_id: str | None = None
    metadata: Mapping[str, str] = field(default_factory=_empty_metadata)


class FileEvidenceAdapter:
    """Capture an existing artifact through the canonical receipt boundary."""

    producer_type: str = "external"

    def __init__(
        self, ingestion: LocalEvidenceIngestionAdapter, context: EvidenceAdapterContext
    ) -> None:
        """Initialize the instance."""
        if not context.producer_id.strip():
            raise ValueError("producer_id must not be blank.")
        self.ingestion = ingestion
        self.context = context

    @classmethod
    def for_root(
        cls, context: EvidenceAdapterContext, *, root: Path = Path(".statewake")
    ) -> FileEvidenceAdapter:
        """Create a first-party adapter with local receipt and content stores."""
        from ..adapters.content_store import ContentAddressedArtifactStore
        from ..adapters.evidence_ingestion import JsonEvidenceReceiptStore

        ingestion = LocalEvidenceIngestionAdapter(
            ContentAddressedArtifactStore(root / "artifacts"),
            JsonEvidenceReceiptStore(root / "receipts"),
        )
        return cls(ingestion, context)

    def ingest(
        self,
        path: Path,
        *,
        captured_at: datetime | None = None,
        source_ref: str | None = None,
    ) -> ExternalEvidenceReceipt:
        """Capture one producer artifact and return its canonical receipt."""
        if captured_at is None:
            captured_at = datetime.now(UTC)
        if captured_at.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware.")
        return self.ingestion.ingest_file(
            path,
            producer_type=self.producer_type,
            producer_id=self.context.producer_id,
            producer_version=self.context.producer_version,
            source_ref=source_ref or path.name,
            source_event_id=self.context.source_event_id,
            run_id=self.context.run_id,
            captured_at=captured_at,
            metadata=dict(self.context.metadata),
        )


class CICDArtifactAdapter(FileEvidenceAdapter):
    """Receipt producer for CI/CD artifacts already created by a pipeline."""

    producer_type = "ci-cd"


class OpenTelemetryTraceAdapter(FileEvidenceAdapter):
    """Receipt producer for an existing OpenTelemetry trace export artifact."""

    producer_type = "opentelemetry"


class AgentRunLogAdapter(FileEvidenceAdapter):
    """Receipt producer for an existing agent/application run-log artifact."""

    producer_type = "agent-run"


class EvaluationOutputAdapter(FileEvidenceAdapter):
    """Receipt producer for an existing evaluator-produced output artifact."""

    producer_type = "evaluation"


class IncidentRecoveryRecordAdapter(FileEvidenceAdapter):
    """Receipt producer for an existing incident/recovery record artifact."""

    producer_type = "incident-recovery"


__all__ = [
    "EvidenceAdapterContext",
    "FileEvidenceAdapter",
    "CICDArtifactAdapter",
    "OpenTelemetryTraceAdapter",
    "AgentRunLogAdapter",
    "EvaluationOutputAdapter",
    "IncidentRecoveryRecordAdapter",
]
