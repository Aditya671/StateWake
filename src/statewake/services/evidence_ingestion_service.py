"""Application services for canonical external-evidence ingestion and verification."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from statewake.utils.json_support import load_object

from ..adapters.content_store import ContentAddressedArtifactStore
from ..adapters.evidence_ingestion import (
    JsonEvidenceReceiptStore,
    LocalEvidenceIngestionAdapter,
)
from ..domain.evidence_receipt import ExternalEvidenceReceipt


def ingest_evidence_file(
    path: Path,
    *,
    artifact_store_root: Path,
    receipt_store_root: Path,
    producer_type: str,
    producer_id: str,
    source_ref: str | None = None,
    source_event_id: str | None = None,
    producer_version: str | None = None,
    run_id: str | None = None,
    captured_at: datetime,
    metadata: dict[str, str] | None = None,
) -> ExternalEvidenceReceipt:
    """Ingest one external artifact idempotently into existing local storage primitives."""
    adapter = LocalEvidenceIngestionAdapter(
        ContentAddressedArtifactStore(artifact_store_root),
        JsonEvidenceReceiptStore(receipt_store_root),
    )
    return adapter.ingest_file(
        path,
        producer_type=producer_type,
        producer_id=producer_id,
        source_ref=source_ref,
        source_event_id=source_event_id,
        producer_version=producer_version,
        run_id=run_id,
        captured_at=captured_at,
        metadata=metadata or {},
    )


def load_evidence_receipt(path: Path) -> ExternalEvidenceReceipt:
    """Load and cryptographically validate one serialized canonical receipt."""
    return ExternalEvidenceReceipt.from_dict(load_object(path))


def verify_evidence_receipt(
    receipt: ExternalEvidenceReceipt,
    *,
    artifact_store_root: Path,
    receipt_store_root: Path,
) -> None:
    """Verify receipt digest, content-addressed artifact, persisted receipt, and size."""
    adapter = LocalEvidenceIngestionAdapter(
        ContentAddressedArtifactStore(artifact_store_root),
        JsonEvidenceReceiptStore(receipt_store_root),
    )
    adapter.verify(receipt)
