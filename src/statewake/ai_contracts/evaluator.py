"""Evaluator evidence contract."""

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
class EvaluatorEvidenceContract:
    """Bind evaluator identity, metric versions, thresholds, and limitations."""

    contract_version: str
    producer_id: str
    run_id: str
    evaluator_id: str
    evaluator_version: str
    metric_version: str
    metric_values: Mapping[str, Any]
    thresholds: Mapping[str, Any]
    dataset_identity: str
    evaluator_limitations: str
    captured_at: datetime
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate evaluator evidence completeness."""
        for field_name in (
            "contract_version",
            "producer_id",
            "run_id",
            "evaluator_id",
            "evaluator_version",
            "metric_version",
            "dataset_identity",
            "evaluator_limitations",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name=field_name)
        if not self.metric_values:
            raise ValueError("metric_values must not be empty.")
        if not self.thresholds:
            raise ValueError("thresholds must not be empty.")
        require_utc_datetime(self.captured_at, field_name="captured_at")
        json_mapping(self.metric_values, field_name="metric_values")
        json_mapping(self.thresholds, field_name="thresholds")
        json_mapping(self.metadata or {}, field_name="metadata")

    def to_dict(self) -> JsonObject:
        """Return the deterministic JSON-compatible contract payload."""
        return {
            "schema_version": AI_CONTRACT_SCHEMA_VERSION,
            "contract_type": "evaluator",
            "contract_version": self.contract_version,
            "producer_id": self.producer_id,
            "run_id": self.run_id,
            "evaluator_id": self.evaluator_id,
            "evaluator_version": self.evaluator_version,
            "metric_version": self.metric_version,
            "metric_values": json_mapping(
                self.metric_values, field_name="metric_values"
            ),
            "thresholds": json_mapping(self.thresholds, field_name="thresholds"),
            "dataset_identity": self.dataset_identity,
            "evaluator_limitations": self.evaluator_limitations,
            "captured_at": datetime_to_json(self.captured_at),
            "metadata": json_mapping(self.metadata or {}, field_name="metadata"),
        }

    def to_evidence_item(self) -> EvidenceItem:
        """Return this contract as a StateWake evidence reference."""
        return evidence_item_from_payload(
            self.to_dict(),
            contract_type="evaluator",
            producer_id=self.producer_id,
            run_id=self.run_id,
        )
