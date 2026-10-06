"""Local, dependency-light adapter for ingesting external evidence artifacts."""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import NotRequired, Protocol, Required, TypedDict, Unpack

from ..adapters.content_store import ContentAddressedArtifactStore
from ..domain.evidence import EvidenceManifest
from ..domain.evidence_receipt import ExternalEvidenceReceipt
from ..domain.governance import (
    SENSITIVITY_ORDER,
    PrivacyGovernanceRuntimeConfig,
    evaluate_evidence_governance,
)
from ..domain.privacy import Redactor
from ..domain.reliability_evidence import EvidenceReference


class _EvidenceIngestionCommonKwargs(TypedDict, total=False):
    """Optional keyword arguments shared by evidence-ingestion operations."""

    producer_version: NotRequired[str | None]
    source_event_id: NotRequired[str | None]
    run_id: NotRequired[str | None]
    metadata: NotRequired[dict[str, str]]
    provenance_ref: NotRequired[EvidenceReference | None]
    sensitivity: NotRequired[str]


class EvidenceIngestionBytesKwargs(_EvidenceIngestionCommonKwargs, total=False):
    """Keyword arguments required when ingesting raw bytes."""

    producer_type: Required[str]
    producer_id: Required[str]
    source_ref: Required[str]
    captured_at: Required[datetime]


class EvidenceIngestionFileKwargs(_EvidenceIngestionCommonKwargs, total=False):
    """Keyword arguments accepted when ingesting a file."""

    producer_type: Required[str]
    producer_id: Required[str]
    source_ref: NotRequired[str | None]
    captured_at: Required[datetime]


EvidenceIngestionKwargs = EvidenceIngestionBytesKwargs


class EvidenceReceiptStore(Protocol):
    """Minimal durable store required by an evidence ingestion adapter."""

    def put(self, receipt: ExternalEvidenceReceipt) -> Path:
        """Persist a receipt idempotently and return its path."""
        ...

    def get(self, receipt_id: str) -> ExternalEvidenceReceipt:
        """Load a receipt by deterministic identity."""
        ...


class JsonEvidenceReceiptStore:
    """Filesystem receipt store keyed by deterministic receipt identity."""

    def __init__(self, root: Path) -> None:
        """Initialize this component with its configured state."""
        self.root = root

    def put(self, receipt: ExternalEvidenceReceipt) -> Path:
        """Persist an evidence receipt while preserving receipt identity semantics."""
        target = self.root / f"{receipt.receipt_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n"
        if target.exists():
            existing = ExternalEvidenceReceipt.from_dict(
                json.loads(target.read_text(encoding="utf-8"))
            )
            if existing.to_dict() == receipt.to_dict():
                return target
            if receipt.source_event_id is not None:
                raise ValueError(
                    f"source_event_id conflict for {receipt.producer_id}:{receipt.source_event_id}."
                )
            raise ValueError(f"receipt identity collision for {receipt.receipt_id}.")

        temporary = target.with_name(
            f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        temporary.write_text(payload, encoding="utf-8")
        try:
            os.link(temporary, target)
        except FileExistsError:
            existing = ExternalEvidenceReceipt.from_dict(
                json.loads(target.read_text(encoding="utf-8"))
            )
            if existing.to_dict() == receipt.to_dict():
                return target
            if receipt.source_event_id is not None:
                raise ValueError(
                    f"source_event_id conflict for {receipt.producer_id}:"
                    f" {receipt.source_event_id}."
                ) from None
            raise ValueError(
                f"receipt identity collision for {receipt.receipt_id}."
            ) from None
        finally:
            temporary.unlink(missing_ok=True)
        return target

    def get(self, receipt_id: str) -> ExternalEvidenceReceipt:
        """Return the requested value."""
        target = self.root / f"{receipt_id}.json"
        if not target.is_file():
            raise FileNotFoundError(f"evidence receipt not found: {receipt_id}")
        return ExternalEvidenceReceipt.from_dict(
            json.loads(target.read_text(encoding="utf-8"))
        )


class EvidenceIngestionAdapter(Protocol):
    """Boundary implemented by external-evidence ingestion integrations."""

    def ingest_bytes(
        self, content: bytes, **kwargs: Unpack[EvidenceIngestionBytesKwargs]
    ) -> ExternalEvidenceReceipt:
        """Capture raw producer bytes and return their canonical evidence receipt."""
        ...

    def ingest_file(
        self, path: Path, **kwargs: Unpack[EvidenceIngestionFileKwargs]
    ) -> ExternalEvidenceReceipt:
        """Capture one producer artifact and return its canonical evidence receipt."""
        ...

    def verify(self, receipt: ExternalEvidenceReceipt) -> None:
        """Verify a persisted receipt and its referenced content."""
        ...


class LocalEvidenceIngestionAdapter:
    """Persist external evidence into existing content-addressed storage and receipts."""

    def __init__(
        self,
        artifact_store: ContentAddressedArtifactStore,
        receipt_store: EvidenceReceiptStore,
        *,
        privacy_governance: PrivacyGovernanceRuntimeConfig | None = None,
    ) -> None:
        """Initialize this component with its configured state."""
        self.artifact_store = artifact_store
        self.receipt_store = receipt_store
        self.privacy_governance = privacy_governance

    def ingest_bytes(
        self, content: bytes, **kwargs: Unpack[EvidenceIngestionBytesKwargs]
    ) -> ExternalEvidenceReceipt:
        """Ingest bytes after privacy redaction and pre-write governance admission."""
        sensitivity = kwargs.get("sensitivity", "internal")
        if sensitivity not in SENSITIVITY_ORDER:
            raise ValueError(
                "sensitivity must be one of public, internal, confidential, restricted."
            )
        metadata = dict(kwargs.get("metadata", {}))
        if self.privacy_governance is not None:
            result = Redactor(self.privacy_governance.privacy_policy).redact_metadata(
                metadata
            )
            metadata = {str(key): str(value) for key, value in result.value.items()}

        digest = sha256(content).hexdigest()
        receipt = ExternalEvidenceReceipt(
            producer_type=kwargs["producer_type"],
            producer_id=kwargs["producer_id"],
            artifact_digest=digest,
            artifact_size=len(content),
            captured_at=kwargs["captured_at"],
            source_ref=kwargs["source_ref"],
            source_event_id=kwargs.get("source_event_id"),
            producer_version=kwargs.get("producer_version"),
            run_id=kwargs.get("run_id"),
            provenance_ref=kwargs.get("provenance_ref"),
            metadata=metadata,
        )
        if self.privacy_governance is not None:
            item = receipt.to_evidence_item(sensitivity=sensitivity)
            manifest = EvidenceManifest(
                manifest_id=receipt.receipt_id,
                run_id=receipt.run_id or receipt.receipt_id,
                items=(item,),
            )
            decision = evaluate_evidence_governance(
                manifest, self.privacy_governance.evidence_policy
            )
            if not decision.storage_allowed:
                raise ValueError(
                    "evidence storage rejected by governance policy: "
                    + "; ".join(decision.storage_reasons)
                )

        stored_digest = self.artifact_store.put(content)
        if stored_digest != digest:
            raise ValueError("content-addressed store returned an unexpected digest")
        self._assert_existing_artifact(receipt)
        self.receipt_store.put(receipt)
        return receipt

    def ingest_file(
        self, path: Path, **kwargs: Unpack[EvidenceIngestionFileKwargs]
    ) -> ExternalEvidenceReceipt:
        """Ingest a file through the canonical content-addressed evidence boundary."""
        if not path.is_file():
            raise FileNotFoundError(path)
        source_ref = kwargs.get("source_ref") or path.name
        metadata = kwargs.get("metadata")
        if metadata is None:
            metadata = {}
        return self.ingest_bytes(
            path.read_bytes(),
            producer_type=kwargs["producer_type"],
            producer_id=kwargs["producer_id"],
            source_ref=source_ref,
            captured_at=kwargs["captured_at"],
            producer_version=kwargs.get("producer_version"),
            source_event_id=kwargs.get("source_event_id"),
            run_id=kwargs.get("run_id"),
            metadata=metadata,
            sensitivity=kwargs.get("sensitivity", "internal"),
        )

    def verify(self, receipt: ExternalEvidenceReceipt) -> None:
        """Verify both receipt structure and referenced content integrity."""
        self._assert_existing_artifact(receipt)
        persisted = self.receipt_store.get(receipt.receipt_id)
        if persisted.to_dict() != receipt.to_dict():
            raise ValueError(
                f"persisted evidence receipt mismatch for {receipt.receipt_id}."
            )

    def _assert_existing_artifact(self, receipt: ExternalEvidenceReceipt) -> None:
        """Verify that an existing content-addressed artifact matches the requested digest and size."""
        content = self.artifact_store.get(receipt.artifact_digest)
        if len(content) != receipt.artifact_size:
            raise ValueError(
                f"evidence artifact size mismatch for {receipt.receipt_id}: "
                f"expected {receipt.artifact_size}, got {len(content)}"
            )
