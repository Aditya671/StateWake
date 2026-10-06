"""Read-only deployment security audit and runtime-containment assurance projections."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass

from statewake.adapters.deployment_security import (
    DEFAULT_PUBLIC_PATHS,
    SECURITY_EVENT_TYPES,
    SECURITY_OPERATIONS,
    SECURITY_REASON_CODES,
)
from statewake.adapters.security_audit import SecurityAuditSnapshot
from statewake.services.runtime_containment_snapshot_service import (
    RuntimeContainmentConfigSnapshot,
)

SECURITY_ASSURANCE_SCHEMA_VERSION = "security-assurance-investigation.v2"
MAX_SECURITY_AUDIT_PAGE_LIMIT = 200
MAX_SECURITY_AUDIT_FILTER_CHARS = 128


def _safe_method(value: str) -> str:
    """Return a bounded method token without exposing arbitrary recorded text."""
    normalized = value.strip().upper()
    if 1 <= len(normalized) <= 16 and normalized.isalpha():
        return normalized
    return "OTHER"


def _route_kind(operation: str | None, path: str) -> str:
    """Classify one protected route without returning the recorded path."""
    if operation == "verify:evidence":
        return "evidence-verification"
    if operation == "verify:proof":
        return "proof-verification"
    if operation in {"review:read", "review:write"}:
        if path == "/api/v1/review-capabilities":
            return "review-capabilities"
        return "claim-review"
    if operation in {"approval:read", "approval:write"}:
        return "claim-approval"
    return "unclassified-recorded-route"


def _safe_reason(value: str) -> str:
    """Return a known reason code or a privacy-safe generic label."""
    if value in SECURITY_REASON_CODES:
        return value
    return "other-recorded-reason"


def _runtime_containment_payload(
    snapshot: RuntimeContainmentConfigSnapshot | None,
) -> dict[str, object]:
    """Project one truthful runtime configuration snapshot without overclaiming enforcement."""
    if snapshot is None:
        return {
            "snapshot_observed": False,
            "configuration_digest": None,
            "recorded_at_utc": None,
            "verification_service": None,
            "limits": None,
            "enforcement": {
                "request_body_bytes": "not-observed",
                "json_input_bytes": "not-observed",
                "json_depth": "not-observed",
                "json_nodes": "not-observed",
                "json_string_bytes": "not-observed",
                "archive_members": "not-observed",
                "archive_uncompressed_bytes": "not-observed",
                "archive_compression_ratio": "not-observed",
                "graph_nodes": "not-observed",
                "verification_seconds": "not-observed",
                "concurrency": "not-observed",
                "temporary_bytes": "not-observed",
            },
            "host_controls_evaluated": False,
        }
    limits = snapshot.runtime_limits
    return {
        "snapshot_observed": True,
        "configuration_digest": snapshot.configuration_digest,
        "recorded_at_utc": snapshot.recorded_at_utc.isoformat(),
        "verification_service": {
            "max_request_bytes": snapshot.max_request_bytes,
            "read_only": snapshot.read_only,
            "require_https": snapshot.require_https,
            "allow_insecure_http": snapshot.allow_insecure_http,
            "artifact_root_count": snapshot.artifact_root_count,
            "artifact_roots_exposed": False,
        },
        "limits": {
            "max_input_bytes": limits.max_input_bytes,
            "max_archive_members": limits.max_archive_members,
            "max_archive_uncompressed_bytes": limits.max_archive_uncompressed_bytes,
            "max_archive_compression_ratio": limits.max_archive_compression_ratio,
            "max_json_depth": limits.max_json_depth,
            "max_json_nodes": limits.max_json_nodes,
            "max_string_bytes": limits.max_string_bytes,
            "max_graph_nodes": limits.max_graph_nodes,
            "max_verification_seconds": limits.max_verification_seconds,
            "max_concurrency": limits.max_concurrency,
            "max_temporary_bytes": limits.max_temporary_bytes,
        },
        "enforcement": {
            "request_body_bytes": "verification-service-enforced",
            "json_input_bytes": "verification-service-enforced",
            "json_depth": "verification-service-enforced",
            "json_nodes": "verification-service-enforced",
            "json_string_bytes": "verification-service-enforced",
            "archive_members": "domain-control-not-wired-to-service-runtime-limits",
            "archive_uncompressed_bytes": "domain-control-not-wired-to-service-runtime-limits",
            "archive_compression_ratio": "domain-control-not-wired-to-service-runtime-limits",
            "graph_nodes": "configured-limit-not-enforced-by-verification-service",
            "verification_seconds": "cooperative-primitive-not-wired-to-verification-service",
            "concurrency": "configured-limit-not-enforced-by-verification-service",
            "temporary_bytes": "configured-limit-not-enforced-by-verification-service",
        },
        "host_controls_evaluated": False,
    }


@dataclass(frozen=True, slots=True)
class SecurityAuditQuery:
    """Allowlisted filters and pagination for security-audit investigation."""

    event: str | None = None
    operation: str | None = None
    reason: str | None = None
    method: str | None = None
    limit: int = 50
    offset: int = 0

    def __post_init__(self) -> None:
        """Validate bounded exact-match filters and pagination."""
        for name, value in (
            ("event", self.event),
            ("operation", self.operation),
            ("reason", self.reason),
            ("method", self.method),
        ):
            if value is not None and (
                not value.strip() or len(value) > MAX_SECURITY_AUDIT_FILTER_CHARS
            ):
                raise ValueError(f"{name} is blank or exceeds the filter limit")
        if self.event is not None and self.event not in SECURITY_EVENT_TYPES:
            raise ValueError("unsupported security audit event")
        if self.operation is not None and self.operation not in SECURITY_OPERATIONS:
            raise ValueError("unsupported security audit operation")
        if self.reason is not None and self.reason not in {
            *SECURITY_REASON_CODES,
            "other-recorded-reason",
        }:
            raise ValueError("unsupported security audit reason")
        if self.method is not None and _safe_method(self.method) != self.method.upper():
            raise ValueError("unsupported security audit method")
        if self.limit < 1 or self.limit > MAX_SECURITY_AUDIT_PAGE_LIMIT:
            raise ValueError(
                f"limit must be between 1 and {MAX_SECURITY_AUDIT_PAGE_LIMIT}"
            )
        if self.offset < 0:
            raise ValueError("offset must be non-negative")

    def to_dict(self) -> dict[str, object]:
        """Return the normalized query contract."""
        return {
            "event": self.event,
            "operation": self.operation,
            "reason": self.reason,
            "method": None if self.method is None else self.method.upper(),
            "limit": self.limit,
            "offset": self.offset,
        }


@dataclass(frozen=True, slots=True)
class SecurityAssuranceProjection:
    """Bounded audit and runtime configuration evidence without host-security inference."""

    snapshot: SecurityAuditSnapshot
    query: SecurityAuditQuery
    read_limit_bytes: int
    record_limit: int
    audit_configured: bool = True
    runtime_snapshot: RuntimeContainmentConfigSnapshot | None = None

    def __post_init__(self) -> None:
        """Validate explicit read ceilings."""
        if self.read_limit_bytes <= 0 or self.record_limit <= 0:
            raise ValueError("security assurance read limits must be positive")

    def to_dict(self) -> dict[str, object]:
        """Return the deterministic privacy-safe assurance projection."""
        rows: list[dict[str, object]] = []
        for record in self.snapshot.records:
            rows.append(
                {
                    "sequence": record.sequence,
                    "occurred_at": record.occurred_at.isoformat(),
                    "event": record.event,
                    "operation": record.operation,
                    "method": _safe_method(record.method),
                    "route_kind": _route_kind(record.operation, record.path),
                    "path_digest": hashlib.sha256(
                        record.path.encode("utf-8")
                    ).hexdigest(),
                    "path_exposed": False,
                    "reason": _safe_reason(record.reason),
                    "reason_digest": hashlib.sha256(
                        record.reason.encode("utf-8")
                    ).hexdigest(),
                    "previous_digest": record.previous_digest,
                    "digest": record.digest,
                }
            )

        normalized_method = (
            None if self.query.method is None else self.query.method.upper()
        )

        def matches(row: dict[str, object]) -> bool:
            """Return whether one safe projected row matches the exact filters."""
            if self.query.event is not None and row["event"] != self.query.event:
                return False
            if (
                self.query.operation is not None
                and row["operation"] != self.query.operation
            ):
                return False
            if self.query.reason is not None and row["reason"] != self.query.reason:
                return False
            if normalized_method is not None and row["method"] != normalized_method:
                return False
            return True

        matched = [row for row in rows if matches(row)]
        page = matched[self.query.offset : self.query.offset + self.query.limit]
        next_offset = self.query.offset + len(page)
        has_more = next_offset < len(matched)
        by_event = Counter(str(row["event"]) for row in rows)
        by_operation = Counter(
            str(row["operation"]) for row in rows if row["operation"] is not None
        )
        by_reason = Counter(str(row["reason"]) for row in rows)
        by_method = Counter(str(row["method"]) for row in rows)
        by_route = Counter(str(row["route_kind"]) for row in rows)
        runtime_payload = _runtime_containment_payload(self.runtime_snapshot)
        return {
            "schema_version": SECURITY_ASSURANCE_SCHEMA_VERSION,
            "source": {
                "resource": "deployment-security-audit-journal",
                "configured": self.audit_configured,
                "exists": self.snapshot.exists,
                "byte_size": self.snapshot.byte_size,
                "read_limit_bytes": self.read_limit_bytes,
                "record_limit": self.record_limit,
                "chain_integrity": (
                    "verified"
                    if self.audit_configured and self.snapshot.exists
                    else "missing"
                ),
                "source_path_exposed": False,
            },
            "observations": {
                "recorded_event_count": len(rows),
                "authentication_failed_count": by_event["authentication_failed"],
                "authorization_denied_count": by_event["authorization_denied"],
                "request_rejected_count": by_event["request_rejected"],
                "request_admitted_count": by_event["request_admitted"],
                "distinct_operation_count": len(by_operation),
                "distinct_route_kind_count": len(by_route),
                "deployment_secure_inferred": False,
                "live_configuration_observed": False,
                "runtime_configuration_snapshot_observed": (
                    self.runtime_snapshot is not None
                ),
            },
            "runtime_containment": runtime_payload,
            "deployment_boundary": {
                "configuration_snapshot_available": False,
                "protected_operations": list(SECURITY_OPERATIONS),
                "default_public_paths": list(DEFAULT_PUBLIC_PATHS),
                "default_require_https": True,
                "authentication_provider": "host-provided",
                "authorization_provider": "host-provided",
                "request_admission_provider": "optional-host-provided",
                "security_event_sink": "optional-host-provided",
                "host_responsibilities": [
                    "tls-termination-and-network-boundary",
                    "real-caller-authentication",
                    "authorization-policy-integration",
                    "tenant-isolation",
                    "kms-hsm-and-secret-custody",
                    "process-container-isolation",
                    "resource-quotas-and-rate-limits",
                    "network-egress-controls",
                ],
            },
            "aggregates": {
                "by_event": [
                    {"event": key, "count": value}
                    for key, value in sorted(by_event.items())
                ],
                "by_operation": [
                    {"operation": key, "count": value}
                    for key, value in sorted(by_operation.items())
                ],
                "by_reason": [
                    {"reason": key, "count": value}
                    for key, value in sorted(by_reason.items())
                ],
                "by_method": [
                    {"method": key, "count": value}
                    for key, value in sorted(by_method.items())
                ],
                "by_route_kind": [
                    {"route_kind": key, "count": value}
                    for key, value in sorted(by_route.items())
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
            "items": page,
            "limitations": [
                "The audit chain proves continuity and content integrity of the records present; it does not prove that every security-relevant host event was captured.",
                "No audit failures recorded does not establish that the deployment is secure or that authentication, authorization, TLS, admission control, or isolation are correctly configured.",
                "A runtime-containment snapshot is emitted from the effective VerificationServiceConfig when explicitly configured; it is configuration evidence captured at service construction, not proof that the process is still live.",
                "Only request-body and bounded-JSON controls are wired to VerificationServiceConfig.runtime_limits today; archive, graph, deadline, concurrency, and temporary-byte values are not promoted into service enforcement claims by this view.",
                "Recorded route paths and arbitrary reason text are not exposed; route categories and digests support bounded correlation without leaking request context.",
                "Host identity provider correctness, tenant isolation, KMS/HSM custody, process isolation, CPU/memory quotas, network egress, and deployment hardening remain external responsibilities.",
            ],
        }

    @property
    def digest(self) -> str:
        """Return the deterministic conditional-read digest."""
        raw = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


def build_security_assurance_projection(
    snapshot: SecurityAuditSnapshot,
    query: SecurityAuditQuery,
    *,
    read_limit_bytes: int,
    record_limit: int,
    audit_configured: bool = True,
    runtime_snapshot: RuntimeContainmentConfigSnapshot | None = None,
) -> SecurityAssuranceProjection:
    """Build one bounded deployment-security and runtime-containment projection."""
    return SecurityAssuranceProjection(
        snapshot,
        query,
        read_limit_bytes,
        record_limit,
        audit_configured,
        runtime_snapshot,
    )


__all__ = [
    "MAX_SECURITY_AUDIT_FILTER_CHARS",
    "MAX_SECURITY_AUDIT_PAGE_LIMIT",
    "SECURITY_ASSURANCE_SCHEMA_VERSION",
    "SecurityAuditQuery",
    "SecurityAssuranceProjection",
    "build_security_assurance_projection",
]
