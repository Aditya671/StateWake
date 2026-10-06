"""Human approval and approval-lifecycle evidence contracts."""

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
from statewake.utils.json_support import (
    JsonObject,
    JsonValue,
    require_object,
    require_string,
)


def _require_sha256(value: str, *, field_name: str) -> None:
    """Require one lowercase SHA-256 identity without inventing normalization."""
    require_non_empty(value, field_name=field_name)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest")


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

    @classmethod
    def from_dict(cls, payload: Mapping[str, JsonValue]) -> HumanApprovalContract:
        """Construct and validate one persisted human-approval contract."""
        if (
            require_string(payload.get("schema_version"), field="schema_version")
            != AI_CONTRACT_SCHEMA_VERSION
        ):
            raise ValueError("unsupported human approval schema version")
        if (
            require_string(payload.get("contract_type"), field="contract_type")
            != "human_approval"
        ):
            raise ValueError("unsupported human approval contract type")
        captured = datetime.fromisoformat(
            require_string(payload.get("captured_at"), field="captured_at").replace(
                "Z", "+00:00"
            )
        )
        metadata_raw = payload.get("metadata", {})
        metadata = dict(require_object(metadata_raw, field="metadata"))
        return cls(
            contract_version=require_string(
                payload.get("contract_version"), field="contract_version"
            ),
            producer_id=require_string(payload.get("producer_id"), field="producer_id"),
            run_id=require_string(payload.get("run_id"), field="run_id"),
            actor_identity_ref=require_string(
                payload.get("actor_identity_ref"), field="actor_identity_ref"
            ),
            role=require_string(payload.get("role"), field="role"),
            approval_action=require_string(
                payload.get("approval_action"), field="approval_action"
            ),
            approval_basis_digest=require_string(
                payload.get("approval_basis_digest"), field="approval_basis_digest"
            ),
            scope=require_string(payload.get("scope"), field="scope"),
            captured_at=captured,
            metadata=metadata,
        )


@dataclass(frozen=True, slots=True)
class HumanApprovalRevocationContract:
    """Record immutable revocation of one exact canonical human approval."""

    contract_version: str
    producer_id: str
    run_id: str
    actor_identity_ref: str
    role: str
    approval_action: str
    approval_basis_digest: str
    scope: str
    target_approval_receipt_id: str
    target_approval_receipt_digest: str
    reason: str
    captured_at: datetime
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate revocation identity, authority, basis, and actor evidence."""
        for field_name in (
            "contract_version",
            "producer_id",
            "run_id",
            "actor_identity_ref",
            "role",
            "approval_action",
            "approval_basis_digest",
            "scope",
            "reason",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name=field_name)
        _require_sha256(
            self.target_approval_receipt_id,
            field_name="target_approval_receipt_id",
        )
        _require_sha256(
            self.target_approval_receipt_digest,
            field_name="target_approval_receipt_digest",
        )
        require_utc_datetime(self.captured_at, field_name="captured_at")
        json_mapping(self.metadata or {}, field_name="metadata")

    def to_dict(self) -> JsonObject:
        """Return the deterministic JSON-compatible revocation payload."""
        return {
            "schema_version": AI_CONTRACT_SCHEMA_VERSION,
            "contract_type": "human_approval_revocation",
            "contract_version": self.contract_version,
            "producer_id": self.producer_id,
            "run_id": self.run_id,
            "actor_identity_ref": self.actor_identity_ref,
            "role": self.role,
            "approval_action": self.approval_action,
            "approval_basis_digest": self.approval_basis_digest,
            "scope": self.scope,
            "target_approval_receipt_id": self.target_approval_receipt_id,
            "target_approval_receipt_digest": self.target_approval_receipt_digest,
            "reason": self.reason,
            "captured_at": datetime_to_json(self.captured_at),
            "metadata": json_mapping(self.metadata or {}, field_name="metadata"),
        }

    def to_evidence_item(self) -> EvidenceItem:
        """Return this revocation as a StateWake evidence reference."""
        return evidence_item_from_payload(
            self.to_dict(),
            contract_type="human_approval_revocation",
            producer_id=self.producer_id,
            run_id=self.run_id,
        )

    @classmethod
    def from_dict(
        cls, payload: Mapping[str, JsonValue]
    ) -> HumanApprovalRevocationContract:
        """Construct and validate one persisted approval-revocation contract."""
        if (
            require_string(payload.get("schema_version"), field="schema_version")
            != AI_CONTRACT_SCHEMA_VERSION
        ):
            raise ValueError("unsupported human approval revocation schema version")
        if (
            require_string(payload.get("contract_type"), field="contract_type")
            != "human_approval_revocation"
        ):
            raise ValueError("unsupported human approval revocation contract type")
        captured = datetime.fromisoformat(
            require_string(payload.get("captured_at"), field="captured_at").replace(
                "Z", "+00:00"
            )
        )
        metadata = dict(require_object(payload.get("metadata", {}), field="metadata"))
        return cls(
            contract_version=require_string(
                payload.get("contract_version"), field="contract_version"
            ),
            producer_id=require_string(payload.get("producer_id"), field="producer_id"),
            run_id=require_string(payload.get("run_id"), field="run_id"),
            actor_identity_ref=require_string(
                payload.get("actor_identity_ref"), field="actor_identity_ref"
            ),
            role=require_string(payload.get("role"), field="role"),
            approval_action=require_string(
                payload.get("approval_action"), field="approval_action"
            ),
            approval_basis_digest=require_string(
                payload.get("approval_basis_digest"), field="approval_basis_digest"
            ),
            scope=require_string(payload.get("scope"), field="scope"),
            target_approval_receipt_id=require_string(
                payload.get("target_approval_receipt_id"),
                field="target_approval_receipt_id",
            ),
            target_approval_receipt_digest=require_string(
                payload.get("target_approval_receipt_digest"),
                field="target_approval_receipt_digest",
            ),
            reason=require_string(payload.get("reason"), field="reason"),
            captured_at=captured,
            metadata=metadata,
        )
