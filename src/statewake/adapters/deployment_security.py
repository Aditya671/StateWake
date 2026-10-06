"""Optional deployment-security boundary for the StateWake HTTP adapter.

This module deliberately does not implement authentication, authorization, TLS
termination, rate limiting, or key custody. Those remain deployment concerns.
Instead, it supplies a small WSGI boundary that requires host/application
providers for those controls before verification requests reach StateWake's
existing read-only verification application.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, Protocol
from wsgiref.types import StartResponse, WSGIApplication, WSGIEnvironment

SecurityOperation = Literal[
    "verify:evidence",
    "verify:proof",
    "review:read",
    "review:write",
    "approval:read",
    "approval:write",
    "approval:revoke",
    "approval:supersede",
]
SECURITY_OPERATIONS: tuple[SecurityOperation, ...] = (
    "verify:evidence",
    "verify:proof",
    "review:read",
    "review:write",
    "approval:read",
    "approval:write",
    "approval:revoke",
    "approval:supersede",
)
SECURITY_EVENT_TYPES = (
    "authentication_failed",
    "authorization_denied",
    "request_rejected",
    "request_admitted",
)
SECURITY_REASON_CODES = (
    "https_required",
    "authentication_failed",
    "authorization_denied",
    "request_admission_rejected",
    "authorized",
)
DEFAULT_PUBLIC_PATHS = ("/health", "/v1/version")
Principal = object


class AuthenticationProvider(Protocol):
    """Resolve the caller identity from the host/application boundary."""

    def __call__(self, environ: WSGIEnvironment) -> Principal | None:
        """Return an authenticated principal or ``None`` when unauthenticated."""


class AuthorizationProvider(Protocol):
    """Authorize one authenticated principal for one StateWake operation."""

    def __call__(
        self,
        principal: Principal,
        operation: SecurityOperation,
        environ: WSGIEnvironment,
    ) -> bool:
        """Return whether the principal may perform the requested operation."""
        ...


class RequestAdmissionProvider(Protocol):
    """Apply deployment-level request admission such as rate limiting."""

    def __call__(
        self,
        principal: Principal | None,
        environ: WSGIEnvironment,
    ) -> bool:
        """Return whether the request may continue to the wrapped application."""
        ...


class SecurityEventSink(Protocol):
    """Receive structured security events without raw request payloads."""

    def __call__(self, event: SecurityEvent) -> None:
        """Record one security event at the deployment boundary."""


@dataclass(frozen=True, slots=True)
class SecurityEvent:
    """Structured deployment security event with non-sensitive request context."""

    event: Literal[
        "authentication_failed",
        "authorization_denied",
        "request_rejected",
        "request_admitted",
    ]
    operation: SecurityOperation | None
    method: str
    path: str
    reason: str


@dataclass(frozen=True, slots=True)
class DeploymentSecurityConfig:
    """Host-supplied security boundary configuration for verification requests."""

    authenticate: AuthenticationProvider
    authorize: AuthorizationProvider
    admit_request: RequestAdmissionProvider | None = None
    security_event_sink: SecurityEventSink | None = None
    require_https: bool = True
    public_paths: tuple[str, ...] = DEFAULT_PUBLIC_PATHS

    def __post_init__(self) -> None:
        """Validate that the deployment boundary cannot disable HTTPS accidentally."""
        if not callable(self.authenticate):
            raise TypeError("authenticate must be callable")
        if not callable(self.authorize):
            raise TypeError("authorize must be callable")
        if self.admit_request is not None and not callable(self.admit_request):
            raise TypeError("admit_request must be callable when provided")
        if self.security_event_sink is not None and not callable(
            self.security_event_sink
        ):
            raise TypeError("security_event_sink must be callable when provided")


def _operation_for_request(method: str, path: str) -> SecurityOperation | None:
    """Return the security operation represented by one supported request."""
    if method == "POST" and path == "/v1/evidence/verify":
        return "verify:evidence"
    if method == "POST" and path == "/v1/proof/verify":
        return "verify:proof"
    parts = [part for part in path.split("/") if part]
    if (
        len(parts) == 5
        and parts[:3] == ["api", "v1", "claims"]
        and len(parts[3]) == 64
        and all(char in "0123456789abcdef" for char in parts[3])
        and parts[4] == "reviews"
    ):
        if method == "GET":
            return "review:read"
        if method == "POST":
            return "review:write"
    if (
        len(parts) == 5
        and parts[:3] == ["api", "v1", "claims"]
        and len(parts[3]) == 64
        and all(char in "0123456789abcdef" for char in parts[3])
        and parts[4] == "approvals"
    ):
        if method == "GET":
            return "approval:read"
        if method == "POST":
            return "approval:write"
    if (
        len(parts) == 7
        and parts[:3] == ["api", "v1", "claims"]
        and len(parts[3]) == 64
        and all(char in "0123456789abcdef" for char in parts[3])
        and parts[4] == "approvals"
        and len(parts[5]) == 64
        and all(char in "0123456789abcdef" for char in parts[5])
        and parts[6] in {"revoke", "supersede"}
        and method == "POST"
    ):
        return "approval:revoke" if parts[6] == "revoke" else "approval:supersede"
    if method == "GET" and path == "/api/v1/review-capabilities":
        return "review:read"
    return None


def _json_error(
    start_response: StartResponse,
    status: str,
    code: str,
    message: str,
) -> list[bytes]:
    """Return a minimal JSON error without echoing untrusted input."""
    import json

    body = (
        json.dumps(
            {"error": {"code": code, "message": message}},
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    start_response(
        status,
        [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


def create_secured_application(
    application: WSGIApplication,
    config: DeploymentSecurityConfig,
) -> WSGIApplication:
    """Wrap the existing verification adapter with host-provided security controls.

    Public health/version routes are delegated without authentication. Verification
    routes require HTTPS, authentication, operation-specific authorization, and the
    optional deployment admission provider. The wrapped StateWake application keeps
    ownership of request-size limits, artifact-root containment, parsing, and
    read-only verification semantics.
    """

    def secured_application(
        environ: WSGIEnvironment,
        start_response: StartResponse,
    ) -> Iterable[bytes]:
        """Apply deployment security policy before invoking the wrapped application."""
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")
        operation = _operation_for_request(method, path)

        if path in config.public_paths:
            return application(environ, start_response)

        if operation is None:
            return application(environ, start_response)

        if (
            config.require_https
            and environ.get("wsgi.url_scheme", "http").lower() != "https"
        ):
            _emit(
                config.security_event_sink,
                SecurityEvent(
                    event="request_rejected",
                    operation=operation,
                    method=method,
                    path=path,
                    reason="https_required",
                ),
            )
            return _json_error(
                start_response,
                "400 Bad Request",
                "HTTPS_REQUIRED",
                "HTTPS is required for verification requests",
            )

        principal = config.authenticate(environ)
        if principal is None:
            _emit(
                config.security_event_sink,
                SecurityEvent(
                    event="authentication_failed",
                    operation=operation,
                    method=method,
                    path=path,
                    reason="authentication_failed",
                ),
            )
            return _json_error(
                start_response,
                "401 Unauthorized",
                "AUTHENTICATION_REQUIRED",
                "authentication is required for verification requests",
            )

        if not config.authorize(principal, operation, environ):
            _emit(
                config.security_event_sink,
                SecurityEvent(
                    event="authorization_denied",
                    operation=operation,
                    method=method,
                    path=path,
                    reason="authorization_denied",
                ),
            )
            return _json_error(
                start_response,
                "403 Forbidden",
                "AUTHORIZATION_DENIED",
                "caller is not authorized for this verification operation",
            )

        if config.admit_request is not None and not config.admit_request(
            principal, environ
        ):
            _emit(
                config.security_event_sink,
                SecurityEvent(
                    event="request_rejected",
                    operation=operation,
                    method=method,
                    path=path,
                    reason="request_admission_rejected",
                ),
            )
            return _json_error(
                start_response,
                "429 Too Many Requests",
                "REQUEST_REJECTED",
                "request admission policy rejected the request",
            )

        _emit(
            config.security_event_sink,
            SecurityEvent(
                event="request_admitted",
                operation=operation,
                method=method,
                path=path,
                reason="authorized",
            ),
        )
        environ["statewake.authenticated_principal"] = principal
        environ["statewake.security_operation"] = operation
        return application(environ, start_response)

    return secured_application


def _emit(sink: SecurityEventSink | None, event: SecurityEvent) -> None:
    """Emit one security event when a host-provided sink exists."""
    if sink is not None:
        sink(event)
