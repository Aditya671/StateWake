"""Tests for deployment security audit investigation projections."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from statewake.adapters.security_audit import SecurityAuditRecord, SecurityAuditSnapshot
from statewake.presentation.security_assurance import (
    SecurityAuditQuery,
    build_security_assurance_projection,
)


def _mapping(value: object) -> dict[str, object]:
    """Narrow one JSON-like projection object for type-safe assertions."""
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _mapping_list(value: object) -> list[dict[str, object]]:
    """Narrow one JSON-like projection list for type-safe assertions."""
    assert isinstance(value, list)
    return cast(list[dict[str, object]], value)


def _record(
    sequence: int,
    *,
    event: str = "request_admitted",
    operation: str | None = "verify:evidence",
    path: str = "/v1/evidence/verify",
    reason: str = "authorized",
    previous_digest: str | None = None,
    digest: str | None = None,
) -> SecurityAuditRecord:
    """Build one already-verified journal record for projection tests."""
    return SecurityAuditRecord(
        sequence=sequence,
        occurred_at=datetime(2026, 9, 29, 12, sequence, tzinfo=UTC),
        event=event,  # type: ignore[arg-type]
        operation=operation,  # type: ignore[arg-type]
        method="POST",
        path=path,
        reason=reason,
        previous_digest=previous_digest,
        digest=digest or f"{sequence + 1:064x}",
    )


def test_projection_keeps_observed_evidence_and_deployment_requirements_distinct() -> (
    None
):
    """Audit history must not become a claim that deployment controls are configured."""
    snapshot = SecurityAuditSnapshot(
        records=(
            _record(0, event="authentication_failed", reason="authentication_failed"),
            _record(1, previous_digest="1" * 64),
        ),
        exists=True,
        byte_size=512,
    )
    payload = build_security_assurance_projection(
        snapshot,
        SecurityAuditQuery(),
        read_limit_bytes=4096,
        record_limit=100,
    ).to_dict()

    observations = _mapping(payload["observations"])
    deployment_boundary = _mapping(payload["deployment_boundary"])
    assert observations["recorded_event_count"] == 2
    assert observations["deployment_secure_inferred"] is False
    assert deployment_boundary["configuration_snapshot_available"] is False
    host_responsibilities = deployment_boundary["host_responsibilities"]
    assert isinstance(host_responsibilities, list)
    assert "real-caller-authentication" in host_responsibilities


def test_projection_redacts_raw_path_and_unknown_reason_text() -> None:
    """Keep arbitrary recorded route/reason strings outside the browser contract."""
    snapshot = SecurityAuditSnapshot(
        records=(
            _record(
                0,
                event="request_rejected",
                operation=None,
                path="/secret/SW_TEST_SECRET_A1",
                reason="SW_TEST_SECRET_A1",
            ),
        ),
        exists=True,
        byte_size=128,
    )
    payload = build_security_assurance_projection(
        snapshot,
        SecurityAuditQuery(),
        read_limit_bytes=4096,
        record_limit=100,
    ).to_dict()
    encoded = str(payload)

    assert "SW_TEST_SECRET_A1" not in encoded
    items = _mapping_list(payload["items"])
    assert items[0]["reason"] == "other-recorded-reason"
    assert items[0]["path_exposed"] is False
    assert len(str(items[0]["path_digest"])) == 64


def test_projection_filters_exact_safe_fields_and_pages() -> None:
    """Apply allowlisted exact filters after privacy-safe projection."""
    snapshot = SecurityAuditSnapshot(
        records=(
            _record(0, event="request_rejected", reason="https_required"),
            _record(
                1,
                event="authorization_denied",
                reason="authorization_denied",
                previous_digest="1" * 64,
            ),
            _record(
                2,
                event="request_admitted",
                reason="authorized",
                previous_digest="2" * 64,
            ),
        ),
        exists=True,
        byte_size=256,
    )
    projection = build_security_assurance_projection(
        snapshot,
        SecurityAuditQuery(event="request_admitted", limit=1, offset=0),
        read_limit_bytes=4096,
        record_limit=100,
    )
    payload = projection.to_dict()

    assert payload["page"] == {
        "limit": 1,
        "offset": 0,
        "returned": 1,
        "matched": 1,
        "has_more": False,
        "next_offset": None,
    }
    items = _mapping_list(payload["items"])
    assert items[0]["sequence"] == 2
    assert len(projection.digest) == 64
