"""Model invocation evidence contract."""

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
    require_optional_reason,
    require_utc_datetime,
)
from statewake.domain.evidence import EvidenceItem
from statewake.utils.json_support import JsonObject


@dataclass(frozen=True, slots=True)
class ModelInvocationContract:
    """Bind model identity, parameters, request, and response evidence."""

    contract_version: str
    producer_id: str
    run_id: str
    provider: str
    model_name: str
    parameters: Mapping[str, Any]
    request_digest: str
    response_digest: str
    captured_at: datetime
    model_version: str | None = None
    model_version_omission_reason: str | None = None
    finish_reason: str | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate model invocation evidence boundaries."""
        for field_name in (
            "contract_version",
            "producer_id",
            "run_id",
            "provider",
            "model_name",
            "request_digest",
            "response_digest",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name=field_name)
        require_optional_reason(
            self.model_version,
            reason=self.model_version_omission_reason,
            field_name="model_version",
        )
        require_utc_datetime(self.captured_at, field_name="captured_at")
        json_mapping(self.parameters, field_name="parameters")
        json_mapping(self.metadata or {}, field_name="metadata")

    def to_dict(self) -> JsonObject:
        """Return the deterministic JSON-compatible contract payload."""
        return {
            "schema_version": AI_CONTRACT_SCHEMA_VERSION,
            "contract_type": "model_invocation",
            "contract_version": self.contract_version,
            "producer_id": self.producer_id,
            "run_id": self.run_id,
            "provider": self.provider,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "model_version_omission_reason": self.model_version_omission_reason,
            "parameters": json_mapping(self.parameters, field_name="parameters"),
            "request_digest": self.request_digest,
            "response_digest": self.response_digest,
            "finish_reason": self.finish_reason,
            "captured_at": datetime_to_json(self.captured_at),
            "metadata": json_mapping(self.metadata or {}, field_name="metadata"),
        }

    def to_evidence_item(self) -> EvidenceItem:
        """Return this contract as a StateWake evidence reference."""
        return evidence_item_from_payload(
            self.to_dict(),
            contract_type="model_invocation",
            producer_id=self.producer_id,
            run_id=self.run_id,
        )
