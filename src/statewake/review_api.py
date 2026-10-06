"""Authenticated append-only review-statement API for the StateWake UI.

This module does not implement a general identity system. It accepts host-supplied
authentication/authorization providers, binds review authorship to the authenticated
principal, and can optionally record canonical ``HumanApprovalContract`` evidence
when a host also supplies explicit approval authority. Review statements and approvals
remain distinct, basis-bound operations and neither mutates the machine decision.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol, cast
from urllib.parse import urlsplit
from wsgiref.simple_server import make_server
from wsgiref.types import StartResponse, WSGIApplication, WSGIEnvironment

from statewake import __version__
from statewake.adapters.deployment_security import (
    DeploymentSecurityConfig,
    Principal,
    SecurityEvent,
    SecurityOperation,
    create_secured_application,
)
from statewake.adapters.human_approval import (
    ApprovalAlreadyRecordedError,
    ApprovalIdempotencyConflictError,
    ApprovalLifecycleConflictError,
    ApprovalLifecycleTargetError,
    HumanApprovalLifecycleItem,
    WorkspaceHumanApprovalStore,
)
from statewake.adapters.review_statement import (
    IdempotencyConflictError,
    JsonlReviewStatementStore,
    ReviewSupersessionError,
)
from statewake.adapters.security_audit import JsonlSecurityAuditStore
from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.domain.review_statement import (
    REVIEW_FINDING_REF_MAX_ITEMS,
    REVIEW_LIMITATION_MAX_CHARS,
    REVIEW_STATEMENT_MAX_CHARS,
    ReviewCategory,
    ReviewStatementRecord,
)
from statewake.presentation.claim_detail import ReportSourceContext
from statewake.read_api import (
    InvalidReportError,
    ReadApiConfig,
    WorkspaceReadError,
    _load_report,
)
from statewake.utils.json_support import loads_object, require_bool, require_string

_DEFAULT_MAX_REQUEST_BYTES = 16_384
_DEFAULT_MAX_STATEMENT_CHARS = REVIEW_STATEMENT_MAX_CHARS
_DEFAULT_MAX_LIMITATION_CHARS = REVIEW_LIMITATION_MAX_CHARS
_DEFAULT_MAX_FINDING_REFS = REVIEW_FINDING_REF_MAX_ITEMS
_DEFAULT_MAX_APPROVAL_REASON_CHARS = 2_000
_DEFAULT_MAX_APPROVAL_RECEIPTS = 2_000


@dataclass(frozen=True, slots=True)
class ReviewActor:
    """Authenticated review identity resolved by the server boundary."""

    identity_ref: str
    role: str

    def __post_init__(self) -> None:
        """Validate the server-owned actor fields."""
        if not self.identity_ref.strip():
            raise ValueError("review actor identity_ref must not be blank")
        if not self.role.strip():
            raise ValueError("review actor role must not be blank")


@dataclass(frozen=True, slots=True)
class ApprovalAuthority:
    """Server-owned authority describing one permitted approval action and scope."""

    producer_id: str
    approval_action: str
    scope: str

    def __post_init__(self) -> None:
        """Reject blank authority fields before any approval route is enabled."""
        for field_name in ("producer_id", "approval_action", "scope"):
            if not str(getattr(self, field_name)).strip():
                raise ValueError(f"approval authority {field_name} must not be blank")


class ApprovalAuthorityProvider(Protocol):
    """Resolve the approval authority available to one authenticated principal."""

    def __call__(
        self,
        principal: Principal,
        report: ReliabilityVerificationReport,
        source: ReportSourceContext,
    ) -> ApprovalAuthority:
        """Return server-owned approval authority for the exact report basis."""
        ...


class ReviewActorProvider(Protocol):
    """Resolve a canonical review actor from one authenticated principal."""

    def __call__(self, principal: Principal) -> ReviewActor:
        """Return the server-owned actor identity and role."""
        ...


class CsrfVerifier(Protocol):
    """Verify the deployment-specific CSRF token for a write request."""

    def __call__(
        self, principal: Principal, token: str, environ: WSGIEnvironment
    ) -> bool:
        """Return whether the supplied anti-CSRF token is valid."""
        ...


def _normalize_origin(value: str) -> str:
    """Return a canonical absolute HTTP(S) origin with no URL path or credentials."""
    text = value.strip()
    try:
        parsed = urlsplit(text)
        _ = parsed.port
    except ValueError as exc:
        raise ValueError(
            "review allowed origins must be valid absolute http(s) origins"
        ) from exc
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("review allowed origins must be absolute http(s) origins only")
    return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"


@dataclass(frozen=True, slots=True)
class ReviewApiConfig:
    """Persistence and bounded-input configuration for human review statements."""

    workspace_root: Path
    review_store_path: Path
    allowed_origins: tuple[str, ...]
    max_request_bytes: int = _DEFAULT_MAX_REQUEST_BYTES
    max_statement_chars: int = _DEFAULT_MAX_STATEMENT_CHARS
    max_limitation_chars: int = _DEFAULT_MAX_LIMITATION_CHARS
    max_finding_refs: int = _DEFAULT_MAX_FINDING_REFS
    max_approval_reason_chars: int = _DEFAULT_MAX_APPROVAL_REASON_CHARS
    max_approval_receipts: int = _DEFAULT_MAX_APPROVAL_RECEIPTS

    def __post_init__(self) -> None:
        """Normalize paths and reject an unsafe write configuration."""
        object.__setattr__(
            self, "workspace_root", self.workspace_root.expanduser().resolve()
        )
        object.__setattr__(
            self, "review_store_path", self.review_store_path.expanduser().resolve()
        )
        origins = tuple(
            _normalize_origin(origin)
            for origin in self.allowed_origins
            if origin.strip()
        )
        if not origins:
            raise ValueError("at least one explicit allowed review origin is required")
        object.__setattr__(self, "allowed_origins", origins)
        for field_name in (
            "max_request_bytes",
            "max_statement_chars",
            "max_limitation_chars",
            "max_finding_refs",
            "max_approval_reason_chars",
            "max_approval_receipts",
        ):
            if int(getattr(self, field_name)) <= 0:
                raise ValueError(f"{field_name} must be positive")
        if self.max_statement_chars > REVIEW_STATEMENT_MAX_CHARS:
            raise ValueError(
                "max_statement_chars exceeds the review record schema limit"
            )
        if self.max_limitation_chars > REVIEW_LIMITATION_MAX_CHARS:
            raise ValueError(
                "max_limitation_chars exceeds the review record schema limit"
            )
        if self.max_finding_refs > REVIEW_FINDING_REF_MAX_ITEMS:
            raise ValueError("max_finding_refs exceeds the review record schema limit")


@dataclass(frozen=True, slots=True)
class ReviewApiSecurity:
    """Host-provided identity, authorization, CSRF, and audit boundary."""

    deployment: DeploymentSecurityConfig
    actor_for_principal: ReviewActorProvider
    verify_csrf: CsrfVerifier
    approval_for_principal: ApprovalAuthorityProvider | None = None

    def __post_init__(self) -> None:
        """Require callable actor and CSRF providers."""
        if not callable(self.actor_for_principal):
            raise TypeError("actor_for_principal must be callable")
        if not callable(self.verify_csrf):
            raise TypeError("verify_csrf must be callable")
        if self.approval_for_principal is not None and not callable(
            self.approval_for_principal
        ):
            raise TypeError("approval_for_principal must be callable when provided")


def _json_response(
    start_response: StartResponse,
    status: str,
    payload: dict[str, object],
    *,
    etag: str | None = None,
) -> list[bytes]:
    """Return one no-store JSON response."""
    body = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ]
    if etag is not None:
        headers.append(("ETag", f'"{etag}"'))
    start_response(status, headers)
    return [body]


def _error(
    start_response: StartResponse,
    status: str,
    code: str,
    message: str,
) -> list[bytes]:
    """Return a stable error without echoing review text or local paths."""
    return _json_response(
        start_response,
        status,
        {"error": {"code": code, "message": message}},
    )


def _review_record_id(path: str) -> str | None:
    """Extract a canonical receipt ID from the exact review-thread route."""
    parts = [part for part in path.split("/") if part]
    if len(parts) != 5 or parts[:3] != ["api", "v1", "claims"] or parts[4] != "reviews":
        return None
    value = parts[3]
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("record id must be a lowercase SHA-256 identity")
    return value


def _approval_record_id(path: str) -> str | None:
    """Extract a canonical receipt ID from the exact human-approval route."""
    parts = [part for part in path.split("/") if part]
    if (
        len(parts) != 5
        or parts[:3] != ["api", "v1", "claims"]
        or parts[4] != "approvals"
    ):
        return None
    value = parts[3]
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("record id must be a lowercase SHA-256 identity")
    return value


def _approval_lifecycle_route(
    path: str,
) -> tuple[str, str, Literal["revoke", "supersede"]] | None:
    """Extract one exact approval lifecycle route without broad collection matching."""
    parts = [part for part in path.split("/") if part]
    if (
        len(parts) != 7
        or parts[:3] != ["api", "v1", "claims"]
        or parts[4] != "approvals"
        or parts[6] not in {"revoke", "supersede"}
    ):
        return None
    record_id, approval_receipt_id = parts[3], parts[5]
    for value, field in (
        (record_id, "record id"),
        (approval_receipt_id, "approval receipt id"),
    ):
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError(f"{field} must be a lowercase SHA-256 identity")
    action = cast(Literal["revoke", "supersede"], parts[6])
    return record_id, approval_receipt_id, action


def _approval_security_operation(path: str) -> SecurityOperation:
    """Return the approval operation used for security-event classification."""
    parts = [part for part in path.split("/") if part]
    if len(parts) == 7 and parts[-1] == "revoke":
        return "approval:revoke"
    if len(parts) == 7 and parts[-1] == "supersede":
        return "approval:supersede"
    return "approval:write"


def _approval_thread_payload(
    record_id: str,
    report: ReliabilityVerificationReport,
    records: list[HumanApprovalLifecycleItem],
    *,
    authority: ApprovalAuthority,
) -> tuple[dict[str, object], str]:
    """Build the exact-basis human-approval evidence thread and digest."""
    payload: dict[str, object] = {
        "schema_version": "human-approval-thread.v1",
        "target": {
            "record_id": record_id,
            "candidate_identity": report.candidate_identity,
            "candidate_digest": report.candidate_digest,
            "report_digest": report.digest,
            "profile_id": report.profile_id,
            "profile_version": report.profile_version,
        },
        "authority": {
            "approval_action": authority.approval_action,
            "scope": authority.scope,
        },
        "items": [record.to_dict() for record in records],
        "active_approval_receipt_ids": [
            record.approval.receipt.receipt_id
            for record in records
            if record.status == "active"
        ],
        "limitations": [
            "Approval evidence is bound to this exact immutable report digest and configured action/scope.",
            "Revocation and supersession append canonical lifecycle evidence; historical approval bytes are never mutated or deleted.",
            "Lifecycle writes do not mutate the verification report, machine decision, publish a release, or expand the configured authority.",
        ],
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload, digest


def _thread_payload(
    record_id: str,
    report: Any,
    records: list[ReviewStatementRecord],
) -> tuple[dict[str, object], str]:
    """Build a deterministic exact-basis review-thread response and ETag."""
    payload: dict[str, object] = {
        "schema_version": "review-thread.v1",
        "target": {
            "record_id": record_id,
            "candidate_identity": report.candidate_identity,
            "candidate_digest": report.candidate_digest,
            "report_digest": report.digest,
            "profile_id": report.profile_id,
            "profile_version": report.profile_version,
        },
        "items": [record.to_dict() for record in records],
        "limitations": [
            "Review statements are human-authored observations and do not alter the machine claim decision.",
            "Review statements are not HumanApprovalContract evidence and do not authorize release or side effects.",
        ],
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return payload, digest


def _read_request_body(environ: WSGIEnvironment, *, limit: int) -> dict[str, Any]:
    """Read one bounded JSON request body using an exact Content-Length."""
    raw_length = environ.get("CONTENT_LENGTH")
    if raw_length in (None, ""):
        raise LengthRequiredError("Content-Length is required")
    try:
        length = int(str(raw_length))
    except ValueError as exc:
        raise ValueError("Content-Length is invalid") from exc
    if length < 0 or length > limit:
        raise RequestTooLargeError("review request exceeds configured maximum")
    stream = environ.get("wsgi.input")
    if stream is None or not hasattr(stream, "read"):
        raise ValueError("request body is unavailable")
    raw = cast(Any, stream).read(length)
    if len(raw) != length:
        raise ValueError("request body is incomplete")
    return dict(loads_object(raw, field="review statement request"))


class LengthRequiredError(ValueError):
    """Raised when a write request omits Content-Length."""


class RequestTooLargeError(OverflowError):
    """Raised when a review request exceeds its configured byte limit."""


class StaleReviewBasisError(ValueError):
    """Raised when a review write is not bound to the exact current report basis."""


def _header(environ: WSGIEnvironment, name: str) -> str:
    """Read one HTTP request header from a WSGI environment."""
    key = "HTTP_" + name.upper().replace("-", "_")
    return str(environ.get(key, "")).strip()


def _emit_rejection(
    security: ReviewApiSecurity,
    *,
    method: str,
    path: str,
    reason: str,
    operation: SecurityOperation = "review:write",
) -> None:
    """Emit one bounded security event for an admitted request rejected later."""
    sink = security.deployment.security_event_sink
    if sink is not None:
        sink(
            SecurityEvent(
                event="request_rejected",
                operation=operation,
                method=method,
                path=path,
                reason=reason,
            )
        )


def _principal(environ: WSGIEnvironment) -> Principal:
    """Return the authenticated principal injected by deployment security."""
    if "statewake.authenticated_principal" not in environ:
        raise PermissionError("authenticated principal is unavailable")
    return environ["statewake.authenticated_principal"]


def _validate_write_protection(
    environ: WSGIEnvironment,
    *,
    config: ReviewApiConfig,
    security: ReviewApiSecurity,
    principal: Principal,
    operation: SecurityOperation = "review:write",
) -> None:
    """Enforce explicit browser-origin and host-supplied CSRF verification."""
    try:
        origin = _normalize_origin(_header(environ, "Origin"))
    except ValueError:
        origin = ""
    if origin not in config.allowed_origins:
        _emit_rejection(
            security,
            method="POST",
            path=str(environ.get("PATH_INFO", "")),
            reason="origin_denied",
            operation=operation,
        )
        raise OriginDeniedError("request origin is not allowed")
    token = _header(environ, "X-StateWake-CSRF")
    if not token or not security.verify_csrf(principal, token, environ):
        _emit_rejection(
            security,
            method="POST",
            path=str(environ.get("PATH_INFO", "")),
            reason="csrf_rejected",
            operation=operation,
        )
        raise CsrfRejectedError("CSRF verification failed")


class InvalidApprovalBasisError(ValueError):
    """Raised when a report cannot support the configured approval operation."""


class ApprovalContextUnavailableError(ValueError):
    """Raised when the source record lacks required approval context such as run ID."""


class OriginDeniedError(PermissionError):
    """Raised when a browser write comes from an untrusted origin."""


class CsrfRejectedError(PermissionError):
    """Raised when deployment-specific CSRF verification fails."""


def _review_category(value: object) -> ReviewCategory:
    """Validate one review-workflow category without approval semantics."""
    text = require_string(value, field="category")
    allowed: tuple[ReviewCategory, ...] = (
        "observation",
        "question",
        "change_requested",
        "finding",
        "review_complete",
    )
    if text not in allowed:
        raise ValueError("unsupported review category")
    return text


def _bounded_text(value: object, *, field: str, max_chars: int) -> str:
    """Return one trimmed non-empty bounded user-authored string."""
    text = require_string(value, field=field).strip()
    if not text:
        raise ValueError(f"{field} must not be blank")
    if len(text) > max_chars:
        raise RequestTooLargeError(f"{field} exceeds configured maximum")
    return text


def _optional_bounded_text(value: object, *, field: str, max_chars: int) -> str | None:
    """Return one optional bounded user-authored string."""
    if value is None:
        return None
    return _bounded_text(value, field=field, max_chars=max_chars)


def _finding_refs(value: object, *, max_items: int) -> tuple[str, ...]:
    """Return a bounded exact list of finding/evidence references."""
    if not isinstance(value, list):
        raise ValueError("finding_refs must be a JSON array")
    if len(value) > max_items:
        raise RequestTooLargeError("finding_refs exceeds configured maximum")
    result: list[str] = []
    for index, item in enumerate(value):
        text = require_string(item, field=f"finding_refs[{index}]").strip()
        if not text or len(text) > 256:
            raise ValueError(
                "finding_refs entries must be non-empty and at most 256 characters"
            )
        result.append(text)
    return tuple(result)


def _exact_digest(value: object, *, field: str) -> str:
    """Return one exact lowercase SHA-256 digest."""
    text = require_string(value, field=field)
    if len(text) != 64 or any(char not in "0123456789abcdef" for char in text):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return text


def create_review_application(
    config: ReviewApiConfig,
    security: ReviewApiSecurity,
) -> WSGIApplication:
    """Create the authenticated review and human-approval API boundary."""
    read_config = ReadApiConfig(config.workspace_root)
    review_store = JsonlReviewStatementStore(config.review_store_path)
    approval_store = WorkspaceHumanApprovalStore(
        config.workspace_root,
        max_receipts=config.max_approval_receipts,
    )

    def application(
        environ: WSGIEnvironment,
        start_response: StartResponse,
    ) -> list[bytes]:
        """Handle one authenticated review or approval request."""
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        try:
            approval_enabled = security.approval_for_principal is not None
            if path == "/health":
                if method != "GET":
                    return _error(
                        start_response,
                        "405 Method Not Allowed",
                        "METHOD_NOT_ALLOWED",
                        "health is read-only",
                    )
                return _json_response(
                    start_response,
                    "200 OK",
                    {
                        "status": "ok",
                        "statewake_version": __version__,
                        "service": "human-review",
                        "approval_write": False,
                    },
                )

            capability_route = path == "/api/v1/review-capabilities"
            review_record_id = None if capability_route else _review_record_id(path)
            approval_record_id = None if capability_route else _approval_record_id(path)
            lifecycle_route = (
                None if capability_route else _approval_lifecycle_route(path)
            )
            lifecycle_record_id = (
                None if lifecycle_route is None else lifecycle_route[0]
            )
            if (
                not capability_route
                and review_record_id is None
                and approval_record_id is None
                and lifecycle_route is None
            ):
                return _error(start_response, "404 Not Found", "NOT_FOUND", "not found")
            if capability_route and method != "GET":
                return _error(
                    start_response,
                    "405 Method Not Allowed",
                    "METHOD_NOT_ALLOWED",
                    "review capabilities are read-only",
                )
            if lifecycle_route is not None and method != "POST":
                return _error(
                    start_response,
                    "405 Method Not Allowed",
                    "METHOD_NOT_ALLOWED",
                    "approval lifecycle transitions are POST-only",
                )
            if (
                lifecycle_route is None
                and (review_record_id is not None or approval_record_id is not None)
                and method not in {"GET", "POST"}
            ):
                return _error(
                    start_response,
                    "405 Method Not Allowed",
                    "METHOD_NOT_ALLOWED",
                    "only GET and POST are supported for human review operations",
                )

            principal = _principal(environ)
            actor = security.actor_for_principal(principal)

            if capability_route:
                review_write = security.deployment.authorize(
                    principal, "review:write", environ
                )
                approval_read = approval_enabled and security.deployment.authorize(
                    principal, "approval:read", environ
                )
                approval_write = approval_enabled and security.deployment.authorize(
                    principal, "approval:write", environ
                )
                approval_revoke = approval_enabled and security.deployment.authorize(
                    principal, "approval:revoke", environ
                )
                approval_supersede = approval_enabled and security.deployment.authorize(
                    principal, "approval:supersede", environ
                )
                approval_capability = None
                if approval_read:
                    approval_capability = {
                        "configured": True,
                        "note": (
                            "Action and scope are resolved server-side for each exact "
                            "report basis; the browser cannot supply approval authority."
                        ),
                    }
                return _json_response(
                    start_response,
                    "200 OK",
                    {
                        "schema_version": "review-capabilities.v1",
                        "mode": "authenticated-human-review",
                        "statewake_version": __version__,
                        "actor": {
                            "identity_ref": actor.identity_ref,
                            "role": actor.role,
                        },
                        "features": {
                            "review_read": True,
                            "review_write": review_write,
                            "approval_read": approval_read,
                            "approval_write": approval_write,
                            "approval_revoke": approval_revoke,
                            "approval_supersede": approval_supersede,
                        },
                        "approval": approval_capability,
                        "limits": {
                            "statement_chars": config.max_statement_chars,
                            "limitation_chars": config.max_limitation_chars,
                            "finding_refs": config.max_finding_refs,
                            "approval_reason_chars": config.max_approval_reason_chars,
                        },
                    },
                )

            record_id = review_record_id or approval_record_id or lifecycle_record_id
            assert record_id is not None
            report, source = _load_report(read_config, record_id)

            if approval_record_id is not None or lifecycle_route is not None:
                if security.approval_for_principal is None:
                    return _error(
                        start_response,
                        "404 Not Found",
                        "APPROVAL_NOT_CONFIGURED",
                        "human approval is not configured for this service",
                    )
                authority = security.approval_for_principal(principal, report, source)
                if approval_record_id is not None and method == "GET":
                    approval_records = approval_store.lifecycle_for_target(
                        record_id,
                        report_digest=report.digest,
                    )
                    payload, digest = _approval_thread_payload(
                        record_id,
                        report,
                        approval_records,
                        authority=authority,
                    )
                    supplied = _header(environ, "If-None-Match")
                    if supplied in {digest, f'"{digest}"'}:
                        start_response(
                            "304 Not Modified",
                            [("ETag", f'"{digest}"'), ("Cache-Control", "no-store")],
                        )
                        return []
                    return _json_response(
                        start_response,
                        "200 OK",
                        payload,
                        etag=digest,
                    )

                lifecycle_action: Literal["revoke", "supersede"] | None = None
                target_approval_receipt_id: str | None = None
                operation: SecurityOperation = "approval:write"
                if lifecycle_route is not None:
                    _, target_approval_receipt_id, lifecycle_action = lifecycle_route
                    operation = (
                        "approval:revoke"
                        if lifecycle_action == "revoke"
                        else "approval:supersede"
                    )
                _validate_write_protection(
                    environ,
                    config=config,
                    security=security,
                    principal=principal,
                    operation=operation,
                )
                if_match = _header(environ, "If-Match")
                if if_match not in {report.digest, f'"{report.digest}"'}:
                    raise StaleReviewBasisError(
                        "If-Match does not name the target report digest"
                    )
                idempotency_key = _header(environ, "Idempotency-Key")
                if not idempotency_key or len(idempotency_key) > 256:
                    raise ValueError("a bounded Idempotency-Key header is required")
                payload = _read_request_body(environ, limit=config.max_request_bytes)
                expected_schema = (
                    "human-approval-input.v1"
                    if lifecycle_action is None
                    else "human-approval-lifecycle-input.v1"
                )
                if payload.get("schema_version") != expected_schema:
                    raise ValueError("unsupported human approval input schema")
                candidate_digest = _exact_digest(
                    payload.get("candidate_digest"), field="candidate_digest"
                )
                report_digest = _exact_digest(
                    payload.get("report_digest"), field="report_digest"
                )
                if (
                    candidate_digest != report.candidate_digest
                    or report_digest != report.digest
                ):
                    raise StaleReviewBasisError(
                        "approval basis does not match the immutable target report"
                    )
                if not require_bool(payload.get("confirmed"), field="confirmed"):
                    raise ValueError(
                        "human approval lifecycle operation requires explicit confirmation"
                    )
                reason = _bounded_text(
                    payload.get("reason"),
                    field="reason",
                    max_chars=config.max_approval_reason_chars,
                )
                if report.approval_status != "requires-human-approval":
                    raise InvalidApprovalBasisError(
                        "report does not require a human approval"
                    )
                if source.run_id is None or not source.run_id.strip():
                    raise ApprovalContextUnavailableError(
                        "report source does not contain a run identifier"
                    )
                common = {
                    "target_record_id": record_id,
                    "candidate_identity": report.candidate_identity,
                    "candidate_digest": report.candidate_digest,
                    "report_digest": report.digest,
                    "profile_id": report.profile_id,
                    "profile_version": report.profile_version,
                    "actor_identity_ref": actor.identity_ref,
                    "actor_role": actor.role,
                    "producer_id": authority.producer_id,
                    "run_id": source.run_id,
                    "approval_action": authority.approval_action,
                    "scope": authority.scope,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                }
                if lifecycle_action == "revoke":
                    assert target_approval_receipt_id is not None
                    revocation, created = approval_store.revoke(
                        target_approval_receipt_id=target_approval_receipt_id,
                        **common,
                    )
                    return _json_response(
                        start_response,
                        "201 Created" if created else "200 OK",
                        {
                            "schema_version": "human-approval-lifecycle-result.v1",
                            "operation": "revoke",
                            "created": created,
                            "revocation": revocation.to_dict(),
                            "approval": None,
                            "effects": {
                                "verification_report_mutated": False,
                                "machine_decision_changed": False,
                                "release_published": False,
                                "side_effect_authorized_outside_scope": False,
                            },
                            "limitations": [
                                "Revocation withdraws only the targeted approval evidence from effective lifecycle use.",
                                "Historical approval and revocation evidence remain immutable and auditable.",
                                "No publication or external side effect is executed by this endpoint.",
                            ],
                        },
                        etag=revocation.receipt.digest,
                    )

                approval_record, created = approval_store.append(
                    supersedes_approval_receipt_id=(
                        target_approval_receipt_id
                        if lifecycle_action == "supersede"
                        else None
                    ),
                    **common,
                )
                if lifecycle_action == "supersede":
                    schema_version = "human-approval-lifecycle-result.v1"
                    response_operation: str | None = "supersede"
                    limitations = [
                        "Supersession appends a replacement approval and retains the predecessor as immutable history.",
                        "Only the replacement remains effective for this exact action, scope, and report basis.",
                        "No publication or external side effect is executed by this endpoint.",
                    ]
                else:
                    schema_version = "human-approval-result.v1"
                    response_operation = None
                    limitations = [
                        "This approval is evidence for the configured action and scope only.",
                        "The immutable verification report remains unchanged.",
                        "No publication or external side effect is executed by this endpoint.",
                    ]
                response: dict[str, object] = {
                    "schema_version": schema_version,
                    "created": created,
                    "approval": approval_record.to_dict(),
                    "effects": {
                        "verification_report_mutated": False,
                        "machine_decision_changed": False,
                        "release_published": False,
                        "side_effect_authorized_outside_scope": False,
                    },
                    "limitations": limitations,
                }
                if response_operation is not None:
                    response["operation"] = response_operation
                    response["revocation"] = None
                return _json_response(
                    start_response,
                    "201 Created" if created else "200 OK",
                    response,
                    etag=approval_record.receipt.digest,
                )

            assert review_record_id is not None
            if method == "GET":
                review_records = review_store.for_target(
                    record_id,
                    report_digest=report.digest,
                )
                payload, digest = _thread_payload(record_id, report, review_records)
                supplied = _header(environ, "If-None-Match")
                if supplied in {digest, f'"{digest}"'}:
                    start_response(
                        "304 Not Modified",
                        [("ETag", f'"{digest}"'), ("Cache-Control", "no-store")],
                    )
                    return []
                return _json_response(start_response, "200 OK", payload, etag=digest)

            _validate_write_protection(
                environ,
                config=config,
                security=security,
                principal=principal,
                operation="review:write",
            )
            if_match = _header(environ, "If-Match")
            if if_match not in {report.digest, f'"{report.digest}"'}:
                raise StaleReviewBasisError(
                    "If-Match does not name the target report digest"
                )
            idempotency_key = _header(environ, "Idempotency-Key")
            if not idempotency_key or len(idempotency_key) > 256:
                raise ValueError("a bounded Idempotency-Key header is required")

            payload = _read_request_body(environ, limit=config.max_request_bytes)
            if payload.get("schema_version") != "review-statement-input.v1":
                raise ValueError("unsupported review statement input schema")
            candidate_digest = _exact_digest(
                payload.get("candidate_digest"), field="candidate_digest"
            )
            report_digest = _exact_digest(
                payload.get("report_digest"), field="report_digest"
            )
            if (
                candidate_digest != report.candidate_digest
                or report_digest != report.digest
            ):
                raise StaleReviewBasisError(
                    "review statement basis does not match the immutable target report"
                )
            statement = _bounded_text(
                payload.get("statement"),
                field="statement",
                max_chars=config.max_statement_chars,
            )
            limitation = _optional_bounded_text(
                payload.get("limitation"),
                field="limitation",
                max_chars=config.max_limitation_chars,
            )
            scope = _bounded_text(payload.get("scope"), field="scope", max_chars=512)
            finding_refs = _finding_refs(
                payload.get("finding_refs", []), max_items=config.max_finding_refs
            )
            supersedes_raw = payload.get("supersedes_digest")
            supersedes = (
                None
                if supersedes_raw is None
                else _exact_digest(supersedes_raw, field="supersedes_digest")
            )
            record, created = review_store.append(
                target_record_id=record_id,
                candidate_identity=report.candidate_identity,
                candidate_digest=report.candidate_digest,
                report_digest=report.digest,
                profile_id=report.profile_id,
                profile_version=report.profile_version,
                actor_identity_ref=actor.identity_ref,
                actor_role=actor.role,
                category=_review_category(payload.get("category")),
                statement=statement,
                finding_refs=finding_refs,
                limitation=limitation,
                scope=scope,
                idempotency_key=idempotency_key,
                supersedes_digest=supersedes,
            )
            return _json_response(
                start_response,
                "201 Created" if created else "200 OK",
                {
                    "schema_version": "review-statement-result.v1",
                    "created": created,
                    "approval_created": False,
                    "review": record.to_dict(),
                },
                etag=record.digest,
            )
        except OriginDeniedError:
            return _error(
                start_response,
                "403 Forbidden",
                "ORIGIN_DENIED",
                "human-review write origin is not allowed",
            )
        except CsrfRejectedError:
            return _error(
                start_response,
                "403 Forbidden",
                "CSRF_REJECTED",
                "human-review write CSRF verification failed",
            )
        except PermissionError:
            return _error(
                start_response,
                "403 Forbidden",
                "APPROVAL_AUTHORITY_DENIED",
                "caller is not authorized for the requested human authority",
            )
        except StaleReviewBasisError:
            stale_operation: SecurityOperation = (
                _approval_security_operation(path)
                if "/approvals" in path
                else "review:write"
            )
            _emit_rejection(
                security,
                method=method,
                path=path,
                reason="stale_human_review_basis",
                operation=stale_operation,
            )
            return _error(
                start_response,
                "409 Conflict",
                "STALE_REVIEW_BASIS",
                "human-review basis no longer matches the requested report",
            )
        except ApprovalIdempotencyConflictError:
            _emit_rejection(
                security,
                method=method,
                path=path,
                reason="approval_idempotency_conflict",
                operation=_approval_security_operation(path),
            )
            return _error(
                start_response,
                "409 Conflict",
                "IDEMPOTENCY_CONFLICT",
                "idempotency key conflicts with a previous approval lifecycle request",
            )
        except ApprovalAlreadyRecordedError:
            return _error(
                start_response,
                "409 Conflict",
                "APPROVAL_ALREADY_RECORDED",
                "approval is already recorded for this actor, action, scope, and basis",
            )
        except ApprovalLifecycleConflictError:
            _emit_rejection(
                security,
                method=method,
                path=path,
                reason="approval_lifecycle_conflict",
                operation=_approval_security_operation(path),
            )
            return _error(
                start_response,
                "409 Conflict",
                "APPROVAL_LIFECYCLE_CONFLICT",
                "approval lifecycle transition conflicts with the current effective state",
            )
        except ApprovalLifecycleTargetError:
            _emit_rejection(
                security,
                method=method,
                path=path,
                reason="approval_lifecycle_target_invalid",
                operation=_approval_security_operation(path),
            )
            return _error(
                start_response,
                "409 Conflict",
                "APPROVAL_LIFECYCLE_TARGET_INVALID",
                "approval lifecycle target does not match the exact report basis or authority",
            )
        except InvalidApprovalBasisError:
            return _error(
                start_response,
                "409 Conflict",
                "APPROVAL_NOT_REQUIRED",
                "the immutable report does not require this human approval",
            )
        except ApprovalContextUnavailableError:
            return _error(
                start_response,
                "409 Conflict",
                "APPROVAL_CONTEXT_UNAVAILABLE",
                "the report source lacks required approval context",
            )
        except IdempotencyConflictError:
            _emit_rejection(
                security, method=method, path=path, reason="idempotency_conflict"
            )
            return _error(
                start_response,
                "409 Conflict",
                "IDEMPOTENCY_CONFLICT",
                "idempotency key conflicts with a previous review request",
            )
        except ReviewSupersessionError:
            _emit_rejection(
                security, method=method, path=path, reason="invalid_supersession"
            )
            return _error(
                start_response,
                "409 Conflict",
                "INVALID_SUPERSESSION",
                "review correction cannot supersede the requested record",
            )
        except LengthRequiredError:
            return _error(
                start_response,
                "411 Length Required",
                "CONTENT_LENGTH_REQUIRED",
                "Content-Length is required for human-review writes",
            )
        except RequestTooLargeError:
            return _error(
                start_response,
                "413 Request Entity Too Large",
                "HUMAN_REVIEW_REQUEST_TOO_LARGE",
                "human-review request exceeds configured limits",
            )
        except FileNotFoundError:
            return _error(
                start_response,
                "404 Not Found",
                "REPORT_NOT_FOUND",
                "requested verification report was not found",
            )
        except WorkspaceReadError:
            return _error(
                start_response,
                "503 Service Unavailable",
                "WORKSPACE_UNAVAILABLE",
                "configured StateWake workspace is unavailable or invalid",
            )
        except InvalidReportError:
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "INVALID_REPORT",
                "requested verification report is invalid",
            )
        except OverflowError:
            return _error(
                start_response,
                "503 Service Unavailable",
                "APPROVAL_SCAN_LIMIT",
                "human approval store exceeds its configured read bound",
            )
        except (OSError, TimeoutError):
            return _error(
                start_response,
                "503 Service Unavailable",
                "HUMAN_REVIEW_STORE_UNAVAILABLE",
                "human review persistence is unavailable",
            )
        except (KeyError, TypeError, ValueError):
            return _error(
                start_response,
                "422 Unprocessable Entity",
                "INVALID_HUMAN_REVIEW_REQUEST",
                "human review request is invalid",
            )

    return create_secured_application(application, security.deployment)


def _required_env(name: str) -> str:
    """Read one required local review-service environment value."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} must be configured for local review writes")
    return value


def _required_secret(name: str) -> str:
    """Read one high-entropy local review secret without inventing a default."""
    value = _required_env(name)
    if len(value) < 32:
        raise ValueError(f"{name} must contain at least 32 characters")
    return value


def create_local_review_application() -> WSGIApplication:
    """Create explicit loopback-oriented single-reviewer development wiring.

    This adapter is intentionally not a multi-user identity provider.  The browser
    proxy keeps its bearer/CSRF tokens server-side, and the actor identity/role are
    supplied by this server configuration rather than by the review form.
    """
    workspace_root = Path(_required_env("STATEWAKE_UI_WORKSPACE_ROOT"))
    review_store = Path(_required_env("STATEWAKE_UI_REVIEW_STORE"))
    bearer_token = _required_secret("STATEWAKE_REVIEW_TOKEN")
    csrf_token = _required_secret("STATEWAKE_REVIEW_CSRF_TOKEN")
    if hmac.compare_digest(bearer_token, csrf_token):
        raise ValueError("review bearer and CSRF secrets must be distinct")
    actor = ReviewActor(
        _required_env("STATEWAKE_REVIEW_ACTOR_ID"),
        _required_env("STATEWAKE_REVIEW_ROLE"),
    )
    approval_values = {
        "producer_id": os.environ.get("STATEWAKE_APPROVAL_PRODUCER_ID", "").strip(),
        "approval_action": os.environ.get("STATEWAKE_APPROVAL_ACTION", "").strip(),
        "scope": os.environ.get("STATEWAKE_APPROVAL_SCOPE", "").strip(),
    }
    approval_authority: ApprovalAuthority | None = None
    if any(approval_values.values()):
        if not all(approval_values.values()):
            raise ValueError(
                "STATEWAKE_APPROVAL_PRODUCER_ID, STATEWAKE_APPROVAL_ACTION, and "
                "STATEWAKE_APPROVAL_SCOPE must be configured together"
            )
        approval_authority = ApprovalAuthority(
            approval_values["producer_id"],
            approval_values["approval_action"],
            approval_values["scope"],
        )
    origins = tuple(
        item.strip()
        for item in _required_env("STATEWAKE_REVIEW_ALLOWED_ORIGINS").split(",")
        if item.strip()
    )
    config = ReviewApiConfig(workspace_root, review_store, origins)

    audit_path = os.environ.get("STATEWAKE_REVIEW_SECURITY_AUDIT", "").strip()
    audit_store = JsonlSecurityAuditStore(Path(audit_path)) if audit_path else None

    def authenticate(environ: WSGIEnvironment) -> ReviewActor | None:
        """Authenticate the local reviewer from a server-held bearer token."""
        supplied = str(environ.get("HTTP_AUTHORIZATION", ""))
        prefix = "Bearer "
        if not supplied.startswith(prefix):
            return None
        token = supplied[len(prefix) :]
        return actor if hmac.compare_digest(token, bearer_token) else None

    def authorize(
        principal: Principal,
        operation: SecurityOperation,
        environ: WSGIEnvironment,
    ) -> bool:
        """Authorize the configured local actor for explicitly enabled operations."""
        del environ
        if principal is not actor:
            return False
        if operation in {"review:read", "review:write"}:
            return True
        return approval_authority is not None and operation in {
            "approval:read",
            "approval:write",
            "approval:revoke",
            "approval:supersede",
        }

    def actor_for_principal(principal: Principal) -> ReviewActor:
        """Resolve the configured server-owned actor from the principal."""
        if principal is not actor:
            raise PermissionError("unexpected review principal")
        return actor

    def verify_csrf(principal: Principal, token: str, environ: WSGIEnvironment) -> bool:
        """Verify the server-held anti-CSRF token for the local actor."""
        del environ
        return principal is actor and hmac.compare_digest(token, csrf_token)

    def approval_for_principal(
        principal: Principal,
        report: ReliabilityVerificationReport,
        source: ReportSourceContext,
    ) -> ApprovalAuthority:
        """Return the explicitly configured local approval authority."""
        del report, source
        if principal is not actor or approval_authority is None:
            raise PermissionError("human approval authority is unavailable")
        return approval_authority

    def security_event_sink(event: SecurityEvent) -> None:
        """Persist bounded security events when an audit path is configured."""
        if audit_store is not None:
            audit_store.append(event)

    deployment = DeploymentSecurityConfig(
        authenticate=authenticate,
        authorize=authorize,
        security_event_sink=security_event_sink,
        require_https=False,
        public_paths=("/health",),
    )
    security = ReviewApiSecurity(
        deployment=deployment,
        actor_for_principal=actor_for_principal,
        verify_csrf=verify_csrf,
        approval_for_principal=(
            approval_for_principal if approval_authority is not None else None
        ),
    )
    return create_review_application(config, security)


def serve(host: str = "127.0.0.1", port: int = 8789) -> None:
    """Run the explicitly configured loopback human-review service."""
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError(
            "the local single-reviewer adapter may bind only to a loopback host"
        )
    application = create_local_review_application()
    with make_server(host, port, application) as httpd:
        print(
            f"StateWake {__version__} human-review API listening on "
            f"http://{host}:{port} (local authenticated review mode)"
        )
        httpd.serve_forever()


if __name__ == "__main__":
    serve()
