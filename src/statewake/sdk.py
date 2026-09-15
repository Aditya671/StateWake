"""Framework-neutral integration SDK for StateWake evidence capture."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from .adapters.content_store import ContentAddressedArtifactStore
from .adapters.evidence_ingestion import (
    EvidenceIngestionAdapter,
    JsonEvidenceReceiptStore,
    LocalEvidenceIngestionAdapter,
)
from .domain.evidence_receipt import ExternalEvidenceReceipt
from .utils.json_support import JsonValue


class StateWakeIntegrationError(Exception):
    """Base class for machine-classifiable integration failures."""


class InvalidEvidenceError(StateWakeIntegrationError):
    """Raised when an integration event cannot be represented as evidence."""


class IdentityConflictError(StateWakeIntegrationError):
    """Raised when an event identity is reused with different content."""


class PersistenceFailureError(StateWakeIntegrationError):
    """Raised when an evidence artifact cannot be persisted."""


def _empty_metadata() -> dict[str, str]:
    """Create an empty string-to-string metadata mapping."""
    return {}


@dataclass(frozen=True, slots=True)
class IntegrationContext:
    """Producer identity and optional execution metadata shared by adapters."""

    producer_id: str
    producer_version: str | None = None
    run_id: str | None = None
    metadata: Mapping[str, str] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        """Validate producer identity and metadata keys."""
        if not self.producer_id.strip():
            raise ValueError("producer_id must not be blank.")
        if self.producer_version is not None and not self.producer_version.strip():
            raise ValueError("producer_version must not be blank when provided.")
        if self.run_id is not None and not self.run_id.strip():
            raise ValueError("run_id must not be blank when provided.")
        if any(not key.strip() for key in self.metadata):
            raise ValueError("metadata keys must not be blank.")


class StateWakeClient:
    """Small application-facing facade over the canonical evidence boundary."""

    def __init__(
        self,
        ingestion: EvidenceIngestionAdapter,
        context: IntegrationContext,
    ) -> None:
        """Initialize the client with an existing or configured ingestion adapter."""
        self._ingestion = ingestion
        self._context = context

    @classmethod
    def for_root(
        cls,
        context: IntegrationContext,
        *,
        root: Path = Path(".statewake"),
    ) -> StateWakeClient:
        """Create a local client using StateWake's content and receipt stores."""
        ingestion = LocalEvidenceIngestionAdapter(
            ContentAddressedArtifactStore(root / "artifacts"),
            JsonEvidenceReceiptStore(root / "receipts"),
        )
        return cls(ingestion, context)

    @property
    def context(self) -> IntegrationContext:
        """Immutable integration context."""
        return self._context

    def ingest_bytes(
        self,
        content: bytes,
        *,
        producer_type: str,
        source_ref: str,
        source_event_id: str | None = None,
        captured_at: datetime | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> ExternalEvidenceReceipt:
        """Capture raw producer bytes through the canonical receipt boundary."""
        if not producer_type.strip():
            raise InvalidEvidenceError("producer_type must not be blank.")
        if not source_ref.strip():
            raise InvalidEvidenceError("source_ref must not be blank.")
        timestamp = captured_at or datetime.now(UTC)
        if timestamp.tzinfo is None:
            raise InvalidEvidenceError("captured_at must be timezone-aware.")
        merged_metadata = dict(self._context.metadata)
        if metadata is not None:
            merged_metadata.update(metadata)
        try:
            return self._ingestion.ingest_bytes(
                content,
                producer_type=producer_type,
                producer_id=self._context.producer_id,
                producer_version=self._context.producer_version,
                source_ref=source_ref,
                source_event_id=source_event_id,
                run_id=self._context.run_id,
                captured_at=timestamp,
                metadata=merged_metadata,
            )
        except ValueError as exc:
            message = str(exc)
            if "identity collision" in message or "source_event_id conflict" in message:
                raise IdentityConflictError(message) from exc
            raise StateWakeIntegrationError(message) from exc
        except OSError as exc:
            raise PersistenceFailureError(str(exc)) from exc

    def ingest_file(
        self,
        path: Path,
        *,
        producer_type: str,
        source_event_id: str | None = None,
        captured_at: datetime | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> ExternalEvidenceReceipt:
        """Capture one existing producer artifact through the canonical boundary."""
        if not path.is_file():
            raise InvalidEvidenceError(f"evidence file does not exist: {path}")
        return self.ingest_bytes(
            path.read_bytes(),
            producer_type=producer_type,
            source_ref=path.name,
            source_event_id=source_event_id,
            captured_at=captured_at,
            metadata=metadata,
        )

    def verify_receipt(self, receipt: ExternalEvidenceReceipt) -> None:
        """Verify the persisted receipt and content-addressed artifact."""
        self._ingestion.verify(receipt)


_JSON_SEPARATORS: Final[tuple[str, str]] = (",", ":")


def _encode_record(record: Mapping[str, JsonValue]) -> bytes:
    """Encode one structured integration record deterministically."""
    try:
        return json.dumps(
            dict(record),
            sort_keys=True,
            separators=_JSON_SEPARATORS,
            ensure_ascii=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise InvalidEvidenceError(
            "integration record is not JSON serializable."
        ) from exc


def _require_id(value: str, field: str) -> str:
    """Require a non-empty integration identity field."""
    if not value.strip():
        raise InvalidEvidenceError(f"{field} must not be blank.")
    return value


@dataclass(frozen=True, slots=True)
class WebhookEvent:
    """HTTP webhook occurrence normalized without interpreting business semantics."""

    request_id: str
    body: bytes
    content_type: str
    signature: str | None = None
    delivery_attempt: int | None = None


class WebhookEvidenceAdapter:
    """Capture webhook bytes and delivery metadata as StateWake evidence."""

    producer_type: Final[str] = "webhook"

    def __init__(self, client: StateWakeClient) -> None:
        """Initialize the adapter."""
        self._client = client

    def ingest(
        self,
        event: WebhookEvent,
        *,
        captured_at: datetime | None = None,
    ) -> ExternalEvidenceReceipt:
        """Capture one webhook occurrence."""
        request_id = _require_id(event.request_id, "request_id")
        if not event.content_type.strip():
            raise InvalidEvidenceError("content_type must not be blank.")
        if event.delivery_attempt is not None and event.delivery_attempt < 1:
            raise InvalidEvidenceError("delivery_attempt must be positive.")
        metadata = {"content_type": event.content_type}
        if event.signature is not None:
            metadata["signature"] = event.signature
        if event.delivery_attempt is not None:
            metadata["delivery_attempt"] = str(event.delivery_attempt)
        return self._client.ingest_bytes(
            event.body,
            producer_type=self.producer_type,
            source_ref=request_id,
            source_event_id=request_id,
            captured_at=captured_at,
            metadata=metadata,
        )


@dataclass(frozen=True, slots=True)
class QueueMessage:
    """Queue delivery metadata preserved independently from payload bytes."""

    message_id: str
    payload: bytes
    delivery_attempt: int = 1
    partition: str | None = None
    sequence_number: int | None = None
    published_at: datetime | None = None


class QueueEvidenceAdapter:
    """Capture queue/event messages without becoming a queue consumer."""

    producer_type: Final[str] = "queue"

    def __init__(self, client: StateWakeClient) -> None:
        """Initialize the adapter."""
        self._client = client

    def ingest(
        self,
        message: QueueMessage,
        *,
        captured_at: datetime | None = None,
    ) -> ExternalEvidenceReceipt:
        """Capture one queue message occurrence."""
        message_id = _require_id(message.message_id, "message_id")
        if message.delivery_attempt < 1:
            raise InvalidEvidenceError("delivery_attempt must be positive.")
        if message.sequence_number is not None and message.sequence_number < 0:
            raise InvalidEvidenceError("sequence_number must be non-negative.")
        metadata = {"delivery_attempt": str(message.delivery_attempt)}
        if message.partition is not None:
            metadata["partition"] = message.partition
        if message.sequence_number is not None:
            metadata["sequence_number"] = str(message.sequence_number)
        if message.published_at is not None:
            if message.published_at.tzinfo is None:
                raise InvalidEvidenceError("published_at must be timezone-aware.")
            metadata["published_at"] = message.published_at.astimezone(UTC).isoformat()
        return self._client.ingest_bytes(
            message.payload,
            producer_type=self.producer_type,
            source_ref=message_id,
            source_event_id=message_id,
            captured_at=captured_at,
            metadata=metadata,
        )


@dataclass(frozen=True, slots=True)
class DatabaseChange:
    """Database mutation observation kept separate from transaction authority."""

    transaction_id: str
    entity_ref: str
    expected_mutation: Mapping[str, JsonValue]
    observed_result: Mapping[str, JsonValue]
    read_at: datetime


class DatabaseEvidenceAdapter:
    """Capture database observations without replacing the source transaction."""

    producer_type: Final[str] = "database"

    def __init__(self, client: StateWakeClient) -> None:
        """Initialize the adapter."""
        self._client = client

    def ingest(
        self,
        change: DatabaseChange,
        *,
        captured_at: datetime | None = None,
    ) -> ExternalEvidenceReceipt:
        """Capture one database observation as structured evidence."""
        transaction_id = _require_id(change.transaction_id, "transaction_id")
        entity_ref = _require_id(change.entity_ref, "entity_ref")
        if change.read_at.tzinfo is None:
            raise InvalidEvidenceError("read_at must be timezone-aware.")
        record: dict[str, JsonValue] = {
            "transaction_id": transaction_id,
            "entity_ref": entity_ref,
            "expected_mutation": dict(change.expected_mutation),
            "observed_result": dict(change.observed_result),
            "read_at": change.read_at.astimezone(UTC).isoformat(),
        }
        return self._client.ingest_bytes(
            _encode_record(record),
            producer_type=self.producer_type,
            source_ref=transaction_id,
            source_event_id=transaction_id,
            captured_at=captured_at,
        )


@dataclass(frozen=True, slots=True)
class BatchRun:
    """Batch execution identity and artifact references."""

    run_id: str
    input_ref: str
    output_ref: str
    schema_version: str | None = None
    row_count: int | None = None
    failure_checkpoint: str | None = None


class BatchEvidenceAdapter:
    """Capture batch/data-pipeline execution evidence."""

    producer_type: Final[str] = "batch"

    def __init__(self, client: StateWakeClient) -> None:
        """Initialize the adapter."""
        self._client = client

    def ingest(
        self,
        run: BatchRun,
        *,
        captured_at: datetime | None = None,
    ) -> ExternalEvidenceReceipt:
        """Capture one batch run as structured evidence."""
        run_id = _require_id(run.run_id, "run_id")
        if run.row_count is not None and run.row_count < 0:
            raise InvalidEvidenceError("row_count must be non-negative.")
        record: dict[str, JsonValue] = {
            "run_id": run_id,
            "input_ref": _require_id(run.input_ref, "input_ref"),
            "output_ref": _require_id(run.output_ref, "output_ref"),
            "schema_version": run.schema_version,
            "row_count": run.row_count,
            "failure_checkpoint": run.failure_checkpoint,
        }
        return self._client.ingest_bytes(
            _encode_record(record),
            producer_type=self.producer_type,
            source_ref=run_id,
            source_event_id=run_id,
            captured_at=captured_at,
        )


@dataclass(frozen=True, slots=True)
class AgentRunEvidence:
    """AI/agent execution references with payload storage controlled by the caller."""

    run_id: str
    model_id: str
    prompt_ref: str | None = None
    retrieval_ref: str | None = None
    tool_call_ref: str | None = None
    tool_result_ref: str | None = None
    policy_decision_ref: str | None = None
    output_ref: str | None = None
    evaluator_ref: str | None = None


class AgentEvidenceAdapter:
    """Capture AI/agent execution references without owning the agent runtime."""

    producer_type: Final[str] = "agent-run"

    def __init__(self, client: StateWakeClient) -> None:
        """Initialize the adapter."""
        self._client = client

    def ingest(
        self,
        run: AgentRunEvidence,
        *,
        captured_at: datetime | None = None,
    ) -> ExternalEvidenceReceipt:
        """Capture one agent execution reference set."""
        run_id = _require_id(run.run_id, "run_id")
        model_id = _require_id(run.model_id, "model_id")
        record: dict[str, JsonValue] = {
            "run_id": run_id,
            "model_id": model_id,
            "prompt_ref": run.prompt_ref,
            "retrieval_ref": run.retrieval_ref,
            "tool_call_ref": run.tool_call_ref,
            "tool_result_ref": run.tool_result_ref,
            "policy_decision_ref": run.policy_decision_ref,
            "output_ref": run.output_ref,
            "evaluator_ref": run.evaluator_ref,
        }
        return self._client.ingest_bytes(
            _encode_record(record),
            producer_type=self.producer_type,
            source_ref=run_id,
            source_event_id=run_id,
            captured_at=captured_at,
        )


__all__ = [
    "AgentEvidenceAdapter",
    "AgentRunEvidence",
    "BatchEvidenceAdapter",
    "BatchRun",
    "DatabaseChange",
    "DatabaseEvidenceAdapter",
    "IdentityConflictError",
    "IntegrationContext",
    "InvalidEvidenceError",
    "PersistenceFailureError",
    "QueueEvidenceAdapter",
    "QueueMessage",
    "StateWakeClient",
    "StateWakeIntegrationError",
    "WebhookEvent",
    "WebhookEvidenceAdapter",
]
