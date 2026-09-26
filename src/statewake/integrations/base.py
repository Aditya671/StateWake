"""Shared helpers for thin Phase 5 producer integrations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from statewake.ai_contracts.base import canonical_json_bytes, sha256_hex
from statewake.domain.evidence import EvidenceItem
from statewake.domain.reliability_evidence import EvidenceReference
from statewake.utils.json_support import JsonObject, require_object, require_value
from statewake.workspace import StateWakeWorkspace
from statewake.workspace.models import WorkspaceRecord


class AIContract(Protocol):
    """Structural protocol for Phase 1 contract objects emitted by integrations."""

    def to_dict(self) -> JsonObject:
        """Return deterministic JSON-compatible contract payload."""
        ...

    def to_evidence_item(self) -> EvidenceItem:
        """Return the contract as a StateWake evidence item."""
        ...


@dataclass(frozen=True, slots=True)
class ContractCaptureResult:
    """One integration-emitted contract with derived payload and evidence identity."""

    contract: AIContract
    payload: JsonObject
    evidence: EvidenceItem

    @property
    def digest(self) -> str:
        """Return the deterministic contract payload digest."""
        if self.evidence.digest is None:
            raise ValueError("captured contract evidence has no digest.")
        return self.evidence.digest

    def persist(self, workspace: StateWakeWorkspace) -> WorkspaceRecord:
        """Persist this contract payload into an explicit StateWake workspace."""
        producer_id = str(self.evidence.metadata.get("producer_id", "unknown"))
        run_id = str(self.evidence.metadata.get("run_id", "unknown"))
        contract_type = str(self.evidence.metadata.get("contract_type", "unknown"))
        captured_value = self.payload.get("captured_at")
        if not isinstance(captured_value, str):
            raise ValueError("captured_at must be an observed UTC timestamp")
        try:
            captured_at = datetime.fromisoformat(captured_value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("captured_at must be a valid UTC timestamp") from exc
        if captured_at.tzinfo is None or captured_at.utcoffset() is None:
            raise ValueError("captured_at must be timezone-aware UTC")
        captured_at = captured_at.astimezone(UTC)
        # The result exposes a mutable JSON payload for compatibility. Never
        # persist bytes that no longer match the evidence issued at capture.
        if sha256_hex(canonical_json_bytes(self.payload)) != self.digest:
            raise ValueError("captured contract payload digest mismatch")
        return workspace.ingest(
            canonical_json_bytes(self.payload),
            producer_type="statewake-integration",
            producer_id=producer_id,
            source_ref=f"ai-contract:{contract_type}:{self.digest}",
            captured_at=captured_at,
            run_id=run_id,
            metadata={
                "contract_type": contract_type,
                "evidence_id": self.evidence.evidence_id,
                "evidence_digest": self.digest,
            },
        )


def capture_contract(contract: AIContract) -> ContractCaptureResult:
    """Return a normalized capture result for a Phase 1 AI contract."""
    payload = contract.to_dict()
    evidence = contract.to_evidence_item()
    return ContractCaptureResult(contract=contract, payload=payload, evidence=evidence)


def digest_json(value: Mapping[str, Any] | str | bytes) -> str:
    """Digest a payload without storing sensitive raw producer content."""
    if isinstance(value, bytes):
        return sha256_hex(value)
    if isinstance(value, str):
        return sha256_hex(value.encode("utf-8"))
    json_value = require_object(value, field="payload")
    return sha256_hex(canonical_json_bytes(json_value))


def json_object_from_mapping(value: Mapping[str, Any], *, field: str) -> JsonObject:
    """Validate a mapping as a JSON object and detach it from producer objects."""
    return dict(require_object(value, field=field))


def optional_string(value: object, *, default: str | None = None) -> str | None:
    """Return a stripped optional string from an arbitrary producer field."""
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def required_string(value: object, *, field: str) -> str:
    """Return a stripped required string from an arbitrary producer field."""
    text = optional_string(value)
    if text is None:
        raise ValueError(f"{field} must not be blank.")
    return text


def mapping_from_object(value: object) -> dict[str, Any]:
    """Read a mapping or simple object attributes without importing its framework."""
    if isinstance(value, Mapping):
        return dict(value)
    result: dict[str, Any] = {}
    for name in dir(value):
        if name.startswith("_"):
            continue
        try:
            item = getattr(value, name)
        except Exception:  # pragma: no cover - defensive producer boundary
            continue
        if callable(item):
            continue
        try:
            require_value(item, field=name)
        except ValueError:
            continue
        result[name] = item
    return result


def profile_evidence_reference(result: ContractCaptureResult) -> EvidenceReference:
    """Return a reliability-chain reference compatible with built-in profiles.

    Phase 1 contract names stay compact (for example ``retrieval``), while Phase 2
    built-in profiles use explicit evidence-role names (for example
    ``retrieval_evidence``). This helper bridges that boundary without changing the
    underlying contract payload or evidence ID.
    """
    contract_type = str(result.evidence.metadata.get("contract_type", "unknown"))
    profile_kind = {
        "prompt": "prompt_evidence",
        "retrieval": "retrieval_evidence",
    }.get(contract_type, contract_type)
    return EvidenceReference(
        kind=f"ai-contract:{profile_kind}",
        identity=result.evidence.evidence_id,
        digest=result.evidence.digest or result.digest,
        source=result.evidence.source,
    )


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for capture boundaries."""
    return datetime.now(UTC)


def parse_time(value: object | None) -> datetime:
    """Parse producer time or return a UTC capture timestamp."""
    if value is None:
        return utc_now()
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("producer timestamp must be timezone-aware.")
        return value.astimezone(UTC)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("producer timestamp must be timezone-aware.")
        return parsed.astimezone(UTC)
    raise ValueError("producer timestamp must be datetime, ISO-8601 string, or None.")


# Explicit admission is intentionally narrower than the list of fields each SDK
# can emit. Unknown names and nested values are discarded, not stringified.
_SAFE_METADATA_FIELDS = frozenset(
    {
        "run_id",
        "producer_id",
        "trace_id",
        "span_id",
        "parent_run_id",
        "parent_span_id",
        "source_event_id",
        "model_name",
        "model_version",
        "tool_name",
        "schema_version",
        "corpus_identity",
        "corpus_snapshot_id",
        "execution_status",
        "side_effect_classification",
        "policy_id",
        "policy_version",
        "decision",
        "evaluator_id",
        "evaluator_version",
        "metric_version",
        "dataset_identity",
        "job_name",
        "artifact_digest",
        "framework",
        "provider",
        "statewake.run_id",
        "statewake.producer_id",
        "gen_ai.operation.name",
        "gen_ai.system",
        "gen_ai.request.model",
        "gen_ai.response.model",
        "retry_of_run_id",
        "recovery_of_run_id",
    }
)


def required_observed_mapping(data: Mapping[str, Any], *, field: str) -> JsonObject:
    """Require a supplied observation; never hash an invented empty payload.

    An explicitly supplied empty object remains valid evidence of emptiness.
    A missing field is unknown, not the same observation.
    """
    if field not in data or data[field] is None:
        raise ValueError(f"{field} was not observed by producer")
    return json_object_from_mapping(data[field], field=field)


def required_observed_time(data: Mapping[str, Any], *, field: str) -> datetime:
    """Require producer time for a duration-bearing runtime event."""
    if field not in data or data[field] is None:
        raise ValueError(f"{field} is required for completed runtime evidence")
    return parse_time(data[field])


def metadata_without_payload(
    data: Mapping[str, Any], *, exclude: set[str]
) -> JsonObject:
    """Admit only bounded, flat producer identity/status metadata.

    The producer is untrusted: a blacklist of ``input``/``output`` aliases
    cannot protect future SDK fields, nested secrets, or exception strings.
    The original event is not mutated; excluded and unrecognized fields are
    intentionally absent rather than represented as evidence of observation.
    """
    metadata: JsonObject = {}
    for key, value in data.items():
        if key in exclude or key not in _SAFE_METADATA_FIELDS:
            continue
        if isinstance(value, bool) or isinstance(value, int):
            metadata[key] = value
        elif isinstance(value, str) and 0 < len(value) <= 256:
            metadata[key] = value
    return metadata
