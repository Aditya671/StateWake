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

SecurityOperation = Literal["verify:evidence", "verify:proof"]
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
    public_paths: tuple[str, ...] = ("/health", "/v1/version")

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


def _operation_for_path(path: str) -> SecurityOperation | None:
    """Return the security operation represented by one verification route."""
    operations: dict[str, SecurityOperation] = {
        "/v1/evidence/verify": "verify:evidence",
        "/v1/proof/verify": "verify:proof",
    }
    return operations.get(path)


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
        operation = _operation_for_path(path)

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
        return application(environ, start_response)

    return secured_application


def _emit(sink: SecurityEventSink | None, event: SecurityEvent) -> None:
    """Emit one security event when a host-provided sink exists."""
    if sink is not None:
        sink(event)
