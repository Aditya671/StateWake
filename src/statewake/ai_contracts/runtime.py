"""Runtime trace evidence contract."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from statewake.ai_contracts.base import (
    AI_CONTRACT_SCHEMA_VERSION,
    datetime_to_json,
    evidence_item_from_payload,
    json_mapping,
    require_non_empty,
    require_utc_datetime,
)
from statewake.domain.evidence import EvidenceItem
from statewake.utils.json_support import JsonObject


@dataclass(frozen=True, slots=True)
class RuntimeTraceContract:
    """Bind runtime trace, span, retry, error, and recovery evidence."""

    contract_version: str
    producer_id: str
    run_id: str
    framework: str
    trace_id: str
    span_id: str
    started_at: datetime
    captured_at: datetime
    parent_run_id: str | None = None
    ended_at: datetime | None = None
    error_status: str | None = None
    retry_of_run_id: str | None = None
    recovery_run_id: str | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate runtime trace evidence completeness."""
        for field_name in (
            "contract_version",
            "producer_id",
            "run_id",
            "framework",
            "trace_id",
            "span_id",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name=field_name)
        require_utc_datetime(self.started_at, field_name="started_at")
        require_utc_datetime(self.captured_at, field_name="captured_at")
        if self.ended_at is not None:
            require_utc_datetime(self.ended_at, field_name="ended_at")
            if self.ended_at < self.started_at:
                raise ValueError("ended_at must not be earlier than started_at.")
        if self.retry_of_run_id is not None:
            require_non_empty(self.retry_of_run_id, field_name="retry_of_run_id")
        if self.recovery_run_id is not None:
            require_non_empty(self.recovery_run_id, field_name="recovery_run_id")
        json_mapping(self.metadata or {}, field_name="metadata")

    def to_dict(self) -> JsonObject:
        """Return the deterministic JSON-compatible contract payload."""
        return {
            "schema_version": AI_CONTRACT_SCHEMA_VERSION,
            "contract_type": "runtime_trace",
            "contract_version": self.contract_version,
            "producer_id": self.producer_id,
            "run_id": self.run_id,
            "parent_run_id": self.parent_run_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "framework": self.framework,
            "started_at": datetime_to_json(self.started_at),
            "ended_at": None
            if self.ended_at is None
            else datetime_to_json(self.ended_at),
            "error_status": self.error_status,
            "retry_of_run_id": self.retry_of_run_id,
            "recovery_run_id": self.recovery_run_id,
            "captured_at": datetime_to_json(self.captured_at),
            "metadata": json_mapping(self.metadata or {}, field_name="metadata"),
        }

    def to_evidence_item(self) -> EvidenceItem:
        """Return this contract as a StateWake evidence reference."""
        return evidence_item_from_payload(
            self.to_dict(),
            contract_type="runtime_trace",
            producer_id=self.producer_id,
            run_id=self.run_id,
        )
