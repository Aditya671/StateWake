"""Retrieval evidence contract."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
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
class RetrievalEvidenceContract:
    """Bind RAG retrieval evidence to corpus, query, chunks, and citations."""

    contract_version: str
    producer_id: str
    run_id: str
    corpus_identity: str
    query_digest: str
    retrieved_item_ids: Sequence[str]
    chunk_digests: Sequence[str]
    citation_boundary: str
    captured_at: datetime
    corpus_digest: str | None = None
    corpus_snapshot_id: str | None = None
    ranking_metadata: Mapping[str, Any] | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate retrieval evidence is reconstructable."""
        for field_name in (
            "contract_version",
            "producer_id",
            "run_id",
            "corpus_identity",
            "query_digest",
            "citation_boundary",
        ):
            require_non_empty(str(getattr(self, field_name)), field_name=field_name)
        if self.corpus_digest is None and self.corpus_snapshot_id is None:
            raise ValueError(
                "retrieval evidence requires corpus_digest or corpus_snapshot_id."
            )
        for field_name, values in (
            ("retrieved_item_ids", self.retrieved_item_ids),
            ("chunk_digests", self.chunk_digests),
        ):
            if not values:
                raise ValueError(f"{field_name} must not be empty.")
            for value in values:
                require_non_empty(str(value), field_name=field_name)
        require_utc_datetime(self.captured_at, field_name="captured_at")
        json_mapping(self.ranking_metadata or {}, field_name="ranking_metadata")
        json_mapping(self.metadata or {}, field_name="metadata")

    def to_dict(self) -> JsonObject:
        """Return the deterministic JSON-compatible contract payload."""
        return {
            "schema_version": AI_CONTRACT_SCHEMA_VERSION,
            "contract_type": "retrieval",
            "contract_version": self.contract_version,
            "producer_id": self.producer_id,
            "run_id": self.run_id,
            "corpus_identity": self.corpus_identity,
            "corpus_digest": self.corpus_digest,
            "corpus_snapshot_id": self.corpus_snapshot_id,
            "query_digest": self.query_digest,
            "retrieved_item_ids": list(self.retrieved_item_ids),
            "chunk_digests": list(self.chunk_digests),
            "ranking_metadata": json_mapping(
                self.ranking_metadata or {}, field_name="ranking_metadata"
            ),
            "citation_boundary": self.citation_boundary,
            "captured_at": datetime_to_json(self.captured_at),
            "metadata": json_mapping(self.metadata or {}, field_name="metadata"),
        }

    def to_evidence_item(self) -> EvidenceItem:
        """Return this contract as a StateWake evidence reference."""
        return evidence_item_from_payload(
            self.to_dict(),
            contract_type="retrieval",
            producer_id=self.producer_id,
            run_id=self.run_id,
        )
