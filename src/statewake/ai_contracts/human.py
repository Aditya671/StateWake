"""Human approval evidence contract."""

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
class HumanApprovalContract:
    """Bind human approval to actor, role, basis, scope, and time."""

    contract_version: str
    producer_id: str
    run_id: str
    actor_identity_ref: str
    role: str
    approval_action: str
    approval_basis_digest: str
    scope: str
    captured_at: datetime
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate human approval evidence completeness."""
        for field_name in (
            "contract_version",
            "producer_id",
            "run_id",
            "actor_identity_ref",
            "role",
            "approval_action",
            "approval_basis_digest",
            "scope",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name=field_name)
        require_utc_datetime(self.captured_at, field_name="captured_at")
        json_mapping(self.metadata or {}, field_name="metadata")

    def to_dict(self) -> JsonObject:
        """Return the deterministic JSON-compatible contract payload."""
        return {
            "schema_version": AI_CONTRACT_SCHEMA_VERSION,
            "contract_type": "human_approval",
            "contract_version": self.contract_version,
            "producer_id": self.producer_id,
            "run_id": self.run_id,
            "actor_identity_ref": self.actor_identity_ref,
            "role": self.role,
            "approval_action": self.approval_action,
            "approval_basis_digest": self.approval_basis_digest,
            "scope": self.scope,
            "captured_at": datetime_to_json(self.captured_at),
            "metadata": json_mapping(self.metadata or {}, field_name="metadata"),
        }

    def to_evidence_item(self) -> EvidenceItem:
        """Return this contract as a StateWake evidence reference."""
        return evidence_item_from_payload(
            self.to_dict(),
            contract_type="human_approval",
            producer_id=self.producer_id,
            run_id=self.run_id,
        )
