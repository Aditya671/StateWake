"""Tests for the optional StateWake deployment security boundary."""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, cast
from wsgiref.types import StartResponse, WSGIEnvironment

from statewake.adapters.deployment_security import (
    AuthenticationProvider,
    AuthorizationProvider,
    DeploymentSecurityConfig,
    RequestAdmissionProvider,
    SecurityEvent,
    SecurityEventSink,
    SecurityOperation,
    create_secured_application,
)
from statewake.adapters.security_audit import JsonlSecurityAuditStore


class _ResponseRecorder:
    """Capture a WSGI response without performing network I/O."""

    def __init__(self) -> None:
        self.status = ""
        self.headers: list[tuple[str, str]] = []

    def __call__(
        self,
        status: str,
        headers: list[tuple[str, str]],
        exc_info: object | None = None,
    ) -> Callable[[bytes], object]:
        """Record the response metadata and return a WSGI write callable."""
        del exc_info
        self.status = status
        self.headers = headers
        return lambda _body: None


_response = _ResponseRecorder()


def _application(
    environ: WSGIEnvironment,
    start_response: StartResponse,
) -> list[bytes]:
    """Represent the existing StateWake application at the wrapper boundary."""
    del environ
    start_response("200 OK", [("Content-Type", "application/json")])
    return [b'{"verified":true}\n']


def _environ(path: str = "/v1/evidence/verify") -> WSGIEnvironment:
    """Build one minimal WSGI verification request."""
    return cast(
        WSGIEnvironment,
        {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": path,
            "wsgi.url_scheme": "https",
        },
    )


def _config(
    authenticate: Callable[[WSGIEnvironment], object | None],
    authorize: Callable[[object, SecurityOperation, WSGIEnvironment], bool],
    admit_request: Callable[[object | None, WSGIEnvironment], bool] | None = None,
    events: list[SecurityEvent] | None = None,
) -> DeploymentSecurityConfig:
    """Build a typed deployment policy for one test."""
    return DeploymentSecurityConfig(
        authenticate=cast(AuthenticationProvider, authenticate),
        authorize=cast(AuthorizationProvider, authorize),
        admit_request=cast(RequestAdmissionProvider, admit_request),
        security_event_sink=(
            cast(SecurityEventSink, events.append) if events is not None else None
        ),
    )


def test_requires_authentication_before_verification() -> None:
    """Reject unauthenticated verification requests and emit a safe event."""
    events: list[SecurityEvent] = []
    application = create_secured_application(
        _application,
        _config(
            lambda _environ: None,
            lambda _principal, _op, _env: True,
            events=events,
        ),
    )

    body = application(_environ(), _response)

    assert _response.status == "401 Unauthorized"
    assert body == [
        b'{"error": {"code": "AUTHENTICATION_REQUIRED", "message": '
        b'"authentication is required for verification requests"}}\n'
    ]
    assert events[-1].reason == "authentication_failed"


def test_authorization_is_operation_specific() -> None:
    """Reject callers who are authenticated but lack the requested operation right."""
    events: list[SecurityEvent] = []
    application = create_secured_application(
        _application,
        _config(
            lambda _environ: "caller",
            lambda _principal, operation, _environ: operation == "verify:proof",
            events=events,
        ),
    )

    application(_environ(), _response)

    assert _response.status == "403 Forbidden"
    assert events[-1].operation == "verify:evidence"
    assert events[-1].reason == "authorization_denied"


def test_admission_provider_can_reject_rate_limited_request() -> None:
    """Allow the deployment to enforce a rate/resource admission decision."""
    application = create_secured_application(
        _application,
        _config(
            lambda _environ: "caller",
            lambda _principal, _operation, _environ: True,
            admit_request=lambda _principal, _environ: False,
        ),
    )

    application(_environ(), _response)

    assert _response.status == "429 Too Many Requests"


def test_success_delegates_to_existing_application() -> None:
    """Preserve the existing application's response after security admission."""
    events: list[SecurityEvent] = []
    application = create_secured_application(
        _application,
        _config(
            lambda _environ: "caller",
            lambda _principal, _operation, _environ: True,
            admit_request=lambda _principal, _environ: True,
            events=events,
        ),
    )

    body = application(_environ(), _response)

    assert _response.status == "200 OK"
    assert body == [b'{"verified":true}\n']
    assert events[-1].event == "request_admitted"


def test_public_health_route_bypasses_application_auth() -> None:
    """Keep public liveness/version endpoints usable by deployment probes."""
    calls: list[str] = []

    def authenticate(_environ: WSGIEnvironment) -> None:
        calls.append("auth")

    application = create_secured_application(
        _application,
        _config(
            authenticate,
            lambda _principal, _operation, _environ: True,
        ),
    )

    application(_environ("/health"), _response)

    assert _response.status == "200 OK"
    assert calls == []


def test_http_is_rejected_before_authentication() -> None:
    """Preserve the fail-closed HTTPS boundary independently of caller identity."""
    calls: list[str] = []

    def authenticate(_environ: WSGIEnvironment) -> str:
        calls.append("auth")
        return "caller"

    application = create_secured_application(
        _application,
        _config(
            authenticate,
            lambda _principal, _operation, _environ: True,
        ),
    )
    environ = _environ()
    environ["wsgi.url_scheme"] = "http"

    application(environ, _response)

    assert _response.status == "400 Bad Request"
    assert calls == []


def test_proof_route_maps_to_distinct_operation() -> None:
    """Pass the proof verification route to operation-specific authorization."""
    seen: list[str] = []

    def authorize(
        _principal: object,
        operation: Literal["verify:evidence", "verify:proof"],
        _environ: WSGIEnvironment,
    ) -> bool:
        seen.append(operation)
        return True

    application = create_secured_application(
        _application,
        _config(
            lambda _environ: "caller",
            authorize,
        ),
    )

    application(_environ("/v1/proof/verify"), _response)

    assert _response.status == "200 OK"
    assert seen == ["verify:proof"]


def test_security_events_do_not_copy_secret_headers_or_request_body() -> None:
    """Keep deployment security telemetry limited to non-sensitive context."""
    events: list[SecurityEvent] = []
    application = create_secured_application(
        _application,
        _config(
            lambda _environ: None, lambda _principal, _op, _env: True, events=events
        ),
    )
    environ = _environ()
    environ["HTTP_AUTHORIZATION"] = "Bearer secret-token"
    environ["wsgi.input"] = type(
        "Input", (), {"read": lambda _self, _n: b"secret-body"}
    )()

    application(environ, _response)

    event = events[-1]
    assert event.event == "authentication_failed"
    assert not hasattr(event, "authorization")
    assert "secret-token" not in repr(event)
    assert "secret-body" not in repr(event)


def test_security_events_can_be_persisted_in_independent_audit_store(tmp_path) -> None:
    """Integrate the boundary event sink with the separate audit storage domain."""
    store = JsonlSecurityAuditStore(tmp_path / "audit" / "security.jsonl")
    # Replace the optional sink with the independently stored audit sink without
    # changing the wrapped StateWake application or its verification semantics.
    config = _config(lambda _environ: None, lambda _principal, _operation, _env: True)

    def persist_event(event: SecurityEvent) -> None:
        store.append(event)

    config = DeploymentSecurityConfig(
        authenticate=config.authenticate,
        authorize=config.authorize,
        security_event_sink=persist_event,
    )
    application = create_secured_application(_application, config)

    application(_environ(), _response)

    records = store.read()
    assert len(records) == 1
    assert records[0].event == "authentication_failed"
    assert records[0].path == "/v1/evidence/verify"
