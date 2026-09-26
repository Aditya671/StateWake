"""Prompt evidence contract."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from statewake.ai_contracts.base import (
    AI_CONTRACT_SCHEMA_VERSION,
    datetime_to_json,
    evidence_item_from_payload,
    json_mapping,
    metadata_field,
    require_non_empty,
    require_utc_datetime,
)
from statewake.domain.evidence import EvidenceItem
from statewake.utils.json_support import JsonObject


@dataclass(frozen=True, slots=True)
class PromptEvidenceContract:
    """Bind prompt construction evidence without storing raw prompt text."""

    contract_version: str
    producer_id: str
    run_id: str
    source: str
    captured_at: datetime
    prompt_template_id: str | None = None
    prompt_template_version: str | None = None
    rendered_prompt_digest: str | None = None
    variables_digest: str | None = None
    redaction_policy_id: str | None = None
    metadata: dict[str, object] = metadata_field()

    def __post_init__(self) -> None:
        """Validate prompt evidence identity and digest boundaries."""
        for field_name in ("contract_version", "producer_id", "run_id", "source"):
            require_non_empty(str(getattr(self, field_name)), field_name=field_name)
        require_utc_datetime(self.captured_at, field_name="captured_at")
        if self.prompt_template_id is None and self.rendered_prompt_digest is None:
            raise ValueError(
                "prompt evidence requires prompt_template_id or rendered_prompt_digest."
            )
        if self.prompt_template_id is not None:
            require_non_empty(self.prompt_template_id, field_name="prompt_template_id")
        if self.prompt_template_version is not None:
            require_non_empty(
                self.prompt_template_version, field_name="prompt_template_version"
            )
        if self.rendered_prompt_digest is not None:
            require_non_empty(
                self.rendered_prompt_digest, field_name="rendered_prompt_digest"
            )
        if self.variables_digest is not None:
            require_non_empty(self.variables_digest, field_name="variables_digest")
        if self.redaction_policy_id is not None:
            require_non_empty(
                self.redaction_policy_id, field_name="redaction_policy_id"
            )
        json_mapping(self.metadata, field_name="metadata")

    def to_dict(self) -> JsonObject:
        """Return the deterministic JSON-compatible contract payload."""
        return {
            "schema_version": AI_CONTRACT_SCHEMA_VERSION,
            "contract_type": "prompt",
            "contract_version": self.contract_version,
            "producer_id": self.producer_id,
            "run_id": self.run_id,
            "source": self.source,
            "captured_at": datetime_to_json(self.captured_at),
            "prompt_template_id": self.prompt_template_id,
            "prompt_template_version": self.prompt_template_version,
            "rendered_prompt_digest": self.rendered_prompt_digest,
            "variables_digest": self.variables_digest,
            "redaction_policy_id": self.redaction_policy_id,
            "metadata": json_mapping(self.metadata, field_name="metadata"),
        }

    def to_evidence_item(self) -> EvidenceItem:
        """Return this contract as a StateWake evidence reference."""
        return evidence_item_from_payload(
            self.to_dict(),
            contract_type="prompt",
            producer_id=self.producer_id,
            run_id=self.run_id,
        )
