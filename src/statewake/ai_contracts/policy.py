"""Policy evidence contract."""

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
class PolicyEvidenceContract:
    """Bind a policy decision to versioned policy evidence and residual risk."""

    contract_version: str
    producer_id: str
    run_id: str
    policy_id: str
    policy_version: str
    decision: str
    rationale_digest: str
    residual_risk: str
    captured_at: datetime
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate policy evidence completeness."""
        for field_name in (
            "contract_version",
            "producer_id",
            "run_id",
            "policy_id",
            "policy_version",
            "decision",
            "rationale_digest",
            "residual_risk",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name=field_name)
        require_utc_datetime(self.captured_at, field_name="captured_at")
        json_mapping(self.metadata or {}, field_name="metadata")

    def to_dict(self) -> JsonObject:
        """Return the deterministic JSON-compatible contract payload."""
        return {
            "schema_version": AI_CONTRACT_SCHEMA_VERSION,
            "contract_type": "policy",
            "contract_version": self.contract_version,
            "producer_id": self.producer_id,
            "run_id": self.run_id,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "decision": self.decision,
            "rationale_digest": self.rationale_digest,
            "residual_risk": self.residual_risk,
            "captured_at": datetime_to_json(self.captured_at),
            "metadata": json_mapping(self.metadata or {}, field_name="metadata"),
        }

    def to_evidence_item(self) -> EvidenceItem:
        """Return this contract as a StateWake evidence reference."""
        return evidence_item_from_payload(
            self.to_dict(),
            contract_type="policy",
            producer_id=self.producer_id,
            run_id=self.run_id,
        )
