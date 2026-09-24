"""Point-in-time state and instrumentation event evidence (not a runtime span)."""

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
class ObservationContract:
    """An observed state/event with no asserted execution start, end or success."""

    contract_version: str
    producer_id: str
    run_id: str
    framework: str
    trace_id: str
    span_id: str
    observation_kind: str
    observed_at: datetime
    parent_run_id: str | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate an observed instant and its identifiers."""
        for name in (
            "contract_version",
            "producer_id",
            "run_id",
            "framework",
            "trace_id",
            "span_id",
            "observation_kind",
        ):
            require_non_empty(str(getattr(self, name)), field_name=name)
        require_utc_datetime(self.observed_at, field_name="observed_at")
        if self.parent_run_id is not None:
            require_non_empty(self.parent_run_id, field_name="parent_run_id")
        json_mapping(self.metadata or {}, field_name="metadata")

    def to_dict(self) -> JsonObject:
        """Return canonical-contract-compatible JSON without duration fields."""
        return {
            "schema_version": AI_CONTRACT_SCHEMA_VERSION,
            "contract_type": "observation",
            "contract_version": self.contract_version,
            "producer_id": self.producer_id,
            "run_id": self.run_id,
            "framework": self.framework,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "observation_kind": self.observation_kind,
            "observed_at": datetime_to_json(self.observed_at),
            "captured_at": datetime_to_json(self.observed_at),
            "parent_run_id": self.parent_run_id,
            "metadata": json_mapping(self.metadata or {}, field_name="metadata"),
        }

    def to_evidence_item(self) -> EvidenceItem:
        """Bind an observation to the existing evidence identity machinery."""
        return evidence_item_from_payload(
            self.to_dict(),
            contract_type="observation",
            producer_id=self.producer_id,
            run_id=self.run_id,
        )
