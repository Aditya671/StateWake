"""Tool-call evidence contract."""

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
class ToolCallContract:
    """Bind a tool call to schema, authorization, input, and output evidence."""

    contract_version: str
    producer_id: str
    run_id: str
    tool_name: str
    schema_version: str
    input_digest: str
    output_digest: str
    execution_status: str
    side_effect_classification: str
    captured_at: datetime
    authorization_decision: str | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate tool-call evidence completeness."""
        for field_name in (
            "contract_version",
            "producer_id",
            "run_id",
            "tool_name",
            "schema_version",
            "input_digest",
            "output_digest",
            "execution_status",
            "side_effect_classification",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name=field_name)
        require_utc_datetime(self.captured_at, field_name="captured_at")
        if (
            self.side_effect_classification != "none"
            and self.authorization_decision is None
        ):
            raise ValueError(
                "side-effecting tool calls require authorization_decision."
            )
        if self.authorization_decision is not None:
            require_non_empty(
                self.authorization_decision, field_name="authorization_decision"
            )
        json_mapping(self.metadata or {}, field_name="metadata")

    def to_dict(self) -> JsonObject:
        """Return the deterministic JSON-compatible contract payload."""
        return {
            "schema_version": AI_CONTRACT_SCHEMA_VERSION,
            "contract_type": "tool_call",
            "contract_version": self.contract_version,
            "producer_id": self.producer_id,
            "run_id": self.run_id,
            "tool_name": self.tool_name,
            "tool_schema_version": self.schema_version,
            "input_digest": self.input_digest,
            "output_digest": self.output_digest,
            "authorization_decision": self.authorization_decision,
            "execution_status": self.execution_status,
            "side_effect_classification": self.side_effect_classification,
            "captured_at": datetime_to_json(self.captured_at),
            "metadata": json_mapping(self.metadata or {}, field_name="metadata"),
        }

    def to_evidence_item(self) -> EvidenceItem:
        """Return this contract as a StateWake evidence reference."""
        return evidence_item_from_payload(
            self.to_dict(),
            contract_type="tool_call",
            producer_id=self.producer_id,
            run_id=self.run_id,
        )
