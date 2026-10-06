"""Bounded read projections for native producer capture failure journals."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass

from statewake.integrations.native_capture import NativeCaptureFailureJournalSnapshot

CAPTURE_HEALTH_SCHEMA_VERSION = "capture-health.v1"
MAX_CAPTURE_FAILURE_PAGE_LIMIT = 200
MAX_CAPTURE_FAILURE_FILTER_CHARS = 128


@dataclass(frozen=True, slots=True)
class CaptureFailureQuery:
    """Allowlisted filters and pagination for failure-journal investigation."""

    stage: str | None = None
    error_type: str | None = None
    limit: int = 50
    offset: int = 0

    def __post_init__(self) -> None:
        """Validate bounded exact-match filters and pagination."""
        for name, value in (("stage", self.stage), ("error_type", self.error_type)):
            if value is not None and (
                not value.strip() or len(value) > MAX_CAPTURE_FAILURE_FILTER_CHARS
            ):
                raise ValueError(f"{name} is blank or exceeds the filter limit")
        if self.limit < 1 or self.limit > MAX_CAPTURE_FAILURE_PAGE_LIMIT:
            raise ValueError(
                f"limit must be between 1 and {MAX_CAPTURE_FAILURE_PAGE_LIMIT}"
            )
        if self.offset < 0:
            raise ValueError("offset must be non-negative")

    def to_dict(self) -> dict[str, object]:
        """Return the normalized query contract."""
        return {
            "stage": self.stage,
            "error_type": self.error_type,
            "limit": self.limit,
            "offset": self.offset,
        }


@dataclass(frozen=True, slots=True)
class CaptureHealthProjection:
    """Read-only failure-journal investigation without inferring capture success."""

    snapshot: NativeCaptureFailureJournalSnapshot
    query: CaptureFailureQuery
    read_limit_bytes: int
    declared_journal_capacity_bytes: int | None = None

    def __post_init__(self) -> None:
        """Validate explicit byte limits and optional operator-declared capacity."""
        if self.read_limit_bytes <= 0:
            raise ValueError("read_limit_bytes must be positive")
        if (
            self.declared_journal_capacity_bytes is not None
            and self.declared_journal_capacity_bytes <= 0
        ):
            raise ValueError("declared journal capacity must be positive")

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic privacy-safe capture-health projection."""
        all_records = self.snapshot.records
        matched = tuple(
            item
            for item in all_records
            if (self.query.stage is None or item.stage == self.query.stage)
            and (
                self.query.error_type is None
                or item.error_type == self.query.error_type
            )
        )
        start = self.query.offset
        page = matched[start : start + self.query.limit]
        next_offset = start + len(page)
        has_more = next_offset < len(matched)
        by_stage = Counter(item.stage for item in all_records)
        by_error_type = Counter(item.error_type for item in all_records)
        capacity = self.declared_journal_capacity_bytes
        if capacity is None:
            capacity_state = "not-declared"
            remaining: int | None = None
        elif self.snapshot.byte_size <= capacity:
            capacity_state = "within-declared-capacity"
            remaining = capacity - self.snapshot.byte_size
        else:
            capacity_state = "exceeds-declared-capacity"
            remaining = 0
        return {
            "schema_version": CAPTURE_HEALTH_SCHEMA_VERSION,
            "source": {
                "resource": "native-capture-failure-journal",
                "journal_exists": self.snapshot.exists,
                "journal_bytes": self.snapshot.byte_size,
                "read_limit_bytes": self.read_limit_bytes,
                "declared_capacity_bytes": capacity,
                "declared_capacity_state": capacity_state,
                "declared_capacity_remaining_bytes": remaining,
            },
            "observations": {
                "recorded_failure_count": len(all_records),
                "distinct_stage_count": len(by_stage),
                "distinct_error_type_count": len(by_error_type),
                "status": (
                    "failures-recorded" if all_records else "no-failures-recorded"
                ),
                "capture_success_inferred": False,
                "workspace_durability_inferred": False,
                "timestamps_available": False,
            },
            "aggregates": {
                "by_stage": [
                    {"stage": key, "count": count}
                    for key, count in sorted(by_stage.items())
                ],
                "by_error_type": [
                    {"error_type": key, "count": count}
                    for key, count in sorted(by_error_type.items())
                ],
            },
            "query": self.query.to_dict(),
            "page": {
                "limit": self.query.limit,
                "offset": self.query.offset,
                "returned": len(page),
                "matched": len(matched),
                "has_more": has_more,
                "next_offset": next_offset if has_more else None,
            },
            "items": [item.to_dict() for item in page],
            "limitations": [
                "Failure-journal entries contain only recorded stage and exception type; raw exception messages and SDK payloads are intentionally absent.",
                "Journal sequence is file order only because the canonical failure journal does not record timestamps.",
                "No recorded failures in this configured journal does not prove successful or complete native capture.",
                "This projection does not observe a live NativeCaptureSink, its in-memory result window, or downstream consumer acknowledgements.",
                "Workspace durability is not inferred from journal contents; durable capture requires the runtime sink to persist a result before acknowledgement.",
            ],
        }

    @property
    def digest(self) -> str:
        """Return the deterministic conditional-read digest."""
        raw = json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


def build_capture_health(
    snapshot: NativeCaptureFailureJournalSnapshot,
    query: CaptureFailureQuery,
    *,
    read_limit_bytes: int,
    declared_journal_capacity_bytes: int | None = None,
) -> CaptureHealthProjection:
    """Build one bounded capture failure-journal investigation projection."""
    return CaptureHealthProjection(
        snapshot,
        query,
        read_limit_bytes,
        declared_journal_capacity_bytes,
    )


__all__ = [
    "CAPTURE_HEALTH_SCHEMA_VERSION",
    "MAX_CAPTURE_FAILURE_FILTER_CHARS",
    "MAX_CAPTURE_FAILURE_PAGE_LIMIT",
    "CaptureFailureQuery",
    "CaptureHealthProjection",
    "build_capture_health",
]
