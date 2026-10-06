"""Immutable human review statements bound to one verification-report basis."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal, cast

from statewake.utils.json_support import JsonObject, require_int, require_string

REVIEW_STATEMENT_MAX_CHARS = 4_000
REVIEW_LIMITATION_MAX_CHARS = 2_000
REVIEW_FINDING_REF_MAX_ITEMS = 32
REVIEW_SCOPE_MAX_CHARS = 512

ReviewCategory = Literal[
    "observation",
    "question",
    "change_requested",
    "finding",
    "review_complete",
]

_ALLOWED_CATEGORIES: tuple[ReviewCategory, ...] = (
    "observation",
    "question",
    "change_requested",
    "finding",
    "review_complete",
)


def _canonical(payload: dict[str, object]) -> bytes:
    """Return the deterministic JSON encoding used by review-record digests."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _require_digest(value: object, *, field: str) -> str:
    """Return a lowercase SHA-256 digest after strict validation."""
    text = require_string(value, field=field)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return text


def _optional_digest(value: object, *, field: str) -> str | None:
    """Return an optional lowercase SHA-256 digest."""
    if value is None:
        return None
    return _require_digest(value, field=field)


def _require_category(value: object) -> ReviewCategory:
    """Return a supported review workflow category without approval semantics."""
    text = require_string(value, field="category")
    if text not in _ALLOWED_CATEGORIES:
        raise ValueError("unsupported review category")
    return text


def _require_non_empty(
    value: object, *, field: str, max_chars: int | None = None
) -> str:
    """Return one trimmed non-empty string with an optional character limit."""
    text = require_string(value, field=field).strip()
    if not text:
        raise ValueError(f"{field} must not be blank")
    if max_chars is not None and len(text) > max_chars:
        raise ValueError(f"{field} exceeds maximum length")
    return text


def _string_tuple(value: object, *, field: str, max_items: int = 32) -> tuple[str, ...]:
    """Return a bounded tuple of non-empty strings from an exact JSON array."""
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a JSON array")
    if len(value) > max_items:
        raise ValueError(f"{field} exceeds maximum item count")
    result: list[str] = []
    for index, item in enumerate(value):
        text = _require_non_empty(item, field=f"{field}[{index}]", max_chars=256)
        result.append(text)
    return tuple(result)


@dataclass(frozen=True, slots=True)
class ReviewStatementRecord:
    """One append-only human-authored review statement.

    This record deliberately carries no approval/rejection authority.  Its category
    is a review-workflow label only, and its actor is supplied by the authenticated
    server boundary rather than by editable client input.
    """

    sequence: int
    target_record_id: str
    candidate_identity: str
    candidate_digest: str
    report_digest: str
    profile_id: str
    profile_version: str
    actor_identity_ref: str
    actor_role: str
    category: ReviewCategory
    statement: str
    finding_refs: tuple[str, ...]
    limitation: str | None
    scope: str
    created_at: datetime
    idempotency_key: str
    request_fingerprint: str
    supersedes_digest: str | None
    previous_digest: str | None
    digest: str

    def __post_init__(self) -> None:
        """Validate immutable review-record invariants."""
        if self.sequence < 0:
            raise ValueError("sequence must be non-negative")
        _require_digest(self.target_record_id, field="target_record_id")
        _require_non_empty(
            self.candidate_identity, field="candidate_identity", max_chars=512
        )
        _require_digest(self.candidate_digest, field="candidate_digest")
        _require_digest(self.report_digest, field="report_digest")
        _require_non_empty(self.profile_id, field="profile_id", max_chars=256)
        _require_non_empty(self.profile_version, field="profile_version", max_chars=128)
        _require_non_empty(
            self.actor_identity_ref, field="actor_identity_ref", max_chars=512
        )
        _require_non_empty(self.actor_role, field="actor_role", max_chars=256)
        _require_category(self.category)
        _require_non_empty(
            self.statement, field="statement", max_chars=REVIEW_STATEMENT_MAX_CHARS
        )
        if len(self.finding_refs) > REVIEW_FINDING_REF_MAX_ITEMS:
            raise ValueError("finding_refs exceeds maximum item count")
        for index, ref in enumerate(self.finding_refs):
            _require_non_empty(ref, field=f"finding_refs[{index}]", max_chars=256)
        if self.limitation is not None:
            _require_non_empty(
                self.limitation,
                field="limitation",
                max_chars=REVIEW_LIMITATION_MAX_CHARS,
            )
        _require_non_empty(self.scope, field="scope", max_chars=REVIEW_SCOPE_MAX_CHARS)
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        _require_non_empty(self.idempotency_key, field="idempotency_key", max_chars=256)
        _require_digest(self.request_fingerprint, field="request_fingerprint")
        _optional_digest(self.supersedes_digest, field="supersedes_digest")
        _optional_digest(self.previous_digest, field="previous_digest")
        _require_digest(self.digest, field="digest")

    def unsigned_payload(self) -> dict[str, object]:
        """Return the canonical digest basis excluding only the record digest."""
        return {
            "schema_version": "review-statement.v1",
            "sequence": self.sequence,
            "target_record_id": self.target_record_id,
            "candidate_identity": self.candidate_identity,
            "candidate_digest": self.candidate_digest,
            "report_digest": self.report_digest,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "actor_identity_ref": self.actor_identity_ref,
            "actor_role": self.actor_role,
            "category": self.category,
            "statement": self.statement,
            "finding_refs": list(self.finding_refs),
            "limitation": self.limitation,
            "scope": self.scope,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
            "idempotency_key": self.idempotency_key,
            "request_fingerprint": self.request_fingerprint,
            "supersedes_digest": self.supersedes_digest,
            "previous_digest": self.previous_digest,
        }

    def to_dict(self) -> JsonObject:
        """Return the canonical JSON-compatible review record."""
        payload = self.unsigned_payload()
        payload["digest"] = self.digest
        return cast(JsonObject, payload)

    def verify(self, *, expected_sequence: int, expected_previous: str | None) -> None:
        """Verify chain position and deterministic record digest."""
        if self.sequence != expected_sequence:
            raise ValueError("review statement sequence is not contiguous")
        if self.previous_digest != expected_previous:
            raise ValueError("review statement chain is discontinuous")
        expected = hashlib.sha256(_canonical(self.unsigned_payload())).hexdigest()
        if self.digest != expected:
            raise ValueError("review statement digest mismatch")

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ReviewStatementRecord:
        """Construct and validate a record from canonical persisted JSON."""
        if payload.get("schema_version") != "review-statement.v1":
            raise ValueError("unsupported review statement schema")
        created_at = datetime.fromisoformat(
            require_string(payload.get("created_at"), field="created_at")
        )
        if created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        limitation_value = payload.get("limitation")
        limitation = (
            None
            if limitation_value is None
            else _require_non_empty(
                limitation_value,
                field="limitation",
                max_chars=REVIEW_LIMITATION_MAX_CHARS,
            )
        )
        return cls(
            sequence=require_int(payload.get("sequence"), field="sequence"),
            target_record_id=_require_digest(
                payload.get("target_record_id"), field="target_record_id"
            ),
            candidate_identity=_require_non_empty(
                payload.get("candidate_identity"),
                field="candidate_identity",
                max_chars=512,
            ),
            candidate_digest=_require_digest(
                payload.get("candidate_digest"), field="candidate_digest"
            ),
            report_digest=_require_digest(
                payload.get("report_digest"), field="report_digest"
            ),
            profile_id=_require_non_empty(
                payload.get("profile_id"), field="profile_id", max_chars=256
            ),
            profile_version=_require_non_empty(
                payload.get("profile_version"), field="profile_version", max_chars=128
            ),
            actor_identity_ref=_require_non_empty(
                payload.get("actor_identity_ref"),
                field="actor_identity_ref",
                max_chars=512,
            ),
            actor_role=_require_non_empty(
                payload.get("actor_role"), field="actor_role", max_chars=256
            ),
            category=_require_category(payload.get("category")),
            statement=_require_non_empty(
                payload.get("statement"),
                field="statement",
                max_chars=REVIEW_STATEMENT_MAX_CHARS,
            ),
            finding_refs=_string_tuple(
                payload.get("finding_refs"),
                field="finding_refs",
                max_items=REVIEW_FINDING_REF_MAX_ITEMS,
            ),
            limitation=limitation,
            scope=_require_non_empty(
                payload.get("scope"),
                field="scope",
                max_chars=REVIEW_SCOPE_MAX_CHARS,
            ),
            created_at=created_at,
            idempotency_key=_require_non_empty(
                payload.get("idempotency_key"), field="idempotency_key", max_chars=256
            ),
            request_fingerprint=_require_digest(
                payload.get("request_fingerprint"), field="request_fingerprint"
            ),
            supersedes_digest=_optional_digest(
                payload.get("supersedes_digest"), field="supersedes_digest"
            ),
            previous_digest=_optional_digest(
                payload.get("previous_digest"), field="previous_digest"
            ),
            digest=_require_digest(payload.get("digest"), field="digest"),
        )


def review_request_fingerprint(
    *,
    target_record_id: str,
    candidate_identity: str,
    candidate_digest: str,
    report_digest: str,
    profile_id: str,
    profile_version: str,
    actor_identity_ref: str,
    actor_role: str,
    category: ReviewCategory,
    statement: str,
    finding_refs: tuple[str, ...],
    limitation: str | None,
    scope: str,
    supersedes_digest: str | None,
) -> str:
    """Return an idempotency comparison digest for one logical review request."""
    payload: dict[str, object] = {
        "target_record_id": target_record_id,
        "candidate_identity": candidate_identity,
        "candidate_digest": candidate_digest,
        "report_digest": report_digest,
        "profile_id": profile_id,
        "profile_version": profile_version,
        "actor_identity_ref": actor_identity_ref,
        "actor_role": actor_role,
        "category": category,
        "statement": statement,
        "finding_refs": list(finding_refs),
        "limitation": limitation,
        "scope": scope,
        "supersedes_digest": supersedes_digest,
    }
    return hashlib.sha256(_canonical(payload)).hexdigest()


def with_review_digest(record: ReviewStatementRecord) -> ReviewStatementRecord:
    """Return a copy of a review record with its canonical digest populated."""
    digest = hashlib.sha256(_canonical(record.unsigned_payload())).hexdigest()
    return ReviewStatementRecord(
        sequence=record.sequence,
        target_record_id=record.target_record_id,
        candidate_identity=record.candidate_identity,
        candidate_digest=record.candidate_digest,
        report_digest=record.report_digest,
        profile_id=record.profile_id,
        profile_version=record.profile_version,
        actor_identity_ref=record.actor_identity_ref,
        actor_role=record.actor_role,
        category=record.category,
        statement=record.statement,
        finding_refs=record.finding_refs,
        limitation=record.limitation,
        scope=record.scope,
        created_at=record.created_at,
        idempotency_key=record.idempotency_key,
        request_fingerprint=record.request_fingerprint,
        supersedes_digest=record.supersedes_digest,
        previous_digest=record.previous_digest,
        digest=digest,
    )


__all__ = [
    "REVIEW_FINDING_REF_MAX_ITEMS",
    "REVIEW_LIMITATION_MAX_CHARS",
    "REVIEW_SCOPE_MAX_CHARS",
    "REVIEW_STATEMENT_MAX_CHARS",
    "ReviewCategory",
    "ReviewStatementRecord",
    "review_request_fingerprint",
    "with_review_digest",
]
