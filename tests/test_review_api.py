"""Security and semantic regression tests for the review-statement HTTP boundary."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from wsgiref.types import WSGIEnvironment

import pytest

from statewake import __version__
from statewake.adapters.deployment_security import (
    AuthenticationProvider,
    AuthorizationProvider,
    DeploymentSecurityConfig,
    SecurityEvent,
    SecurityEventSink,
    SecurityOperation,
)
from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.reports.json_report import render_json_report
from statewake.review_api import (
    ApprovalAuthority,
    ApprovalAuthorityProvider,
    CsrfVerifier,
    ReviewActor,
    ReviewApiConfig,
    ReviewApiSecurity,
    create_review_application,
)
from statewake.workspace.workspace import StateWakeWorkspace


def _report(**changes: object) -> ReliabilityVerificationReport:
    """Create one canonical report fixture requiring a human decision."""
    values: dict[str, object] = {
        "format_version": "1",
        "claim": "RAG answer verified",
        "decision": "review",
        "profile_id": "rag_answer_verified.v1",
        "profile_version": "1",
        "verified": False,
        "evidence_included": ("run", "retrieval"),
        "evidence_omitted": (),
        "evidence_missing": (),
        "checks_passed": ("chain_verified",),
        "checks_failed": (),
        "checks_unrun": ("human-review",),
        "checks_unknown": (),
        "source_identities": ("run-1",),
        "artifact_digests": ("a" * 64,),
        "rationale": ("Human interpretation remains required.",),
        "caveats": ("This report is not an approval.",),
        "residual_risks": (),
        "human_decisions_required": ("Reviewer decision",),
        "allowed_use": ("Human inspection",),
        "prohibited_use": ("Automatic approval",),
        "machine_readable_appendix": (),
        "recovery_status": "not-applicable",
        "verifier_version": "statewake-test",
        "generated_at": "2026-09-27T00:00:00+00:00",
        "candidate_identity": "candidate-1",
        "candidate_digest": "b" * 64,
        "report_type": "engineering",
        "profile_evaluation_digest": "c" * 64,
        "approval_status": "requires-human-approval",
    }
    values.update(changes)
    return ReliabilityVerificationReport(**values)  # type: ignore[arg-type]


def _workspace_report(
    tmp_path: Path,
) -> tuple[Path, str, ReliabilityVerificationReport]:
    """Persist one canonical report through the real workspace ingestion path."""
    root = tmp_path / "workspace"
    workspace = StateWakeWorkspace.open(root)
    report = _report()
    record = workspace.ingest(
        render_json_report(report).encode("utf-8"),
        producer_type="statewake-verification-report",
        producer_id="statewake.test",
        source_ref="report.json",
        source_event_id="report-1",
        run_id="run-1",
        captured_at=datetime(2026, 9, 27, tzinfo=UTC),
        metadata={"candidate_identity": report.candidate_identity},
    )
    workspace.verify(record)
    workspace.close()
    return root, record.record_id, report


def _secured_app(
    tmp_path: Path,
    *,
    authorize_write: bool = True,
    csrf_ok: bool = True,
    events: list[SecurityEvent] | None = None,
    public_health: bool = False,
    approval_enabled: bool = False,
):
    """Create an authenticated review API fixture with server-owned actor identity."""
    root, record_id, report = _workspace_report(tmp_path)
    actor = ReviewActor("reviewer:alice", "reliability-reviewer")

    def authenticate(_environ: WSGIEnvironment) -> ReviewActor | None:
        """Authenticate only the synthetic bearer used by these tests."""
        return (
            actor if _environ.get("HTTP_AUTHORIZATION") == "Bearer test-token" else None
        )

    def authorize(
        _principal: object,
        operation: SecurityOperation,
        _environ: WSGIEnvironment,
    ) -> bool:
        """Allow reads and conditionally allow configured human-review writes."""
        if operation == "review:read":
            return True
        if operation == "review:write":
            return authorize_write
        if operation == "approval:read":
            return approval_enabled
        if operation in {"approval:write", "approval:revoke", "approval:supersede"}:
            return approval_enabled and authorize_write
        return False

    def actor_for_principal(principal: object) -> ReviewActor:
        """Return the server-resolved actor rather than any client field."""
        assert principal is actor
        return actor

    def verify_csrf(
        principal: object,
        token: str,
        _environ: WSGIEnvironment,
    ) -> bool:
        """Apply the synthetic anti-CSRF policy for this test boundary."""
        return principal is actor and csrf_ok and token == "csrf-token"

    def approval_for_principal(
        principal: object,
        _report: ReliabilityVerificationReport,
        _source: object,
    ) -> ApprovalAuthority:
        """Return one fixed test approval authority from the trusted server boundary."""
        assert principal is actor
        return ApprovalAuthority(
            "statewake.test.approver",
            "approve-release-evidence",
            "candidate release evidence",
        )

    event_sink: SecurityEventSink | None = None
    if events is not None:

        def record_security_event(event: SecurityEvent) -> None:
            events.append(event)

        event_sink = record_security_event

    deployment = DeploymentSecurityConfig(
        authenticate=cast(AuthenticationProvider, authenticate),
        authorize=cast(AuthorizationProvider, authorize),
        security_event_sink=event_sink,
        require_https=False,
        public_paths=(("/health",) if public_health else ()),
    )
    application = create_review_application(
        ReviewApiConfig(
            root,
            tmp_path / "reviews" / "review-statements.jsonl",
            ("http://localhost:3000",),
        ),
        ReviewApiSecurity(
            deployment,
            actor_for_principal,
            cast(CsrfVerifier, verify_csrf),
            approval_for_principal=(
                cast(ApprovalAuthorityProvider, approval_for_principal)
                if approval_enabled
                else None
            ),
        ),
    )
    return application, record_id, report


def _require_header_list(value: object) -> list[tuple[str, str]]:
    """Narrow captured WSGI response headers for type-safe assertions."""
    assert isinstance(value, list)
    assert all(
        isinstance(item, tuple)
        and len(item) == 2
        and isinstance(item[0], str)
        and isinstance(item[1], str)
        for item in value
    )
    return [(item[0], item[1]) for item in value]


def _request(
    application: Any,
    path: str,
    *,
    method: str = "GET",
    body: dict[str, object] | None = None,
    authenticated: bool = True,
    origin: str = "http://localhost:3000",
    csrf: str = "csrf-token",
    if_match: str | None = None,
    idempotency_key: str | None = None,
) -> tuple[str, dict[str, str], dict[str, Any]]:
    """Invoke one WSGI request and require the review API JSON-object response."""
    raw = b"" if body is None else json.dumps(body).encode("utf-8")
    environ: dict[str, object] = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "CONTENT_LENGTH": str(len(raw)),
        "wsgi.input": io.BytesIO(raw),
        "wsgi.url_scheme": "http",
        "HTTP_ORIGIN": origin,
        "HTTP_X_STATEWAKE_CSRF": csrf,
    }
    if authenticated:
        environ["HTTP_AUTHORIZATION"] = "Bearer test-token"
    if if_match is not None:
        environ["HTTP_IF_MATCH"] = if_match
    if idempotency_key is not None:
        environ["HTTP_IDEMPOTENCY_KEY"] = idempotency_key
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    result = b"".join(application(cast(WSGIEnvironment, environ), start_response))
    assert result, "review API tests require a JSON response body"
    decoded = json.loads(result)
    assert isinstance(decoded, dict)
    return (
        str(captured["status"]),
        dict(_require_header_list(captured.get("headers"))),
        cast(dict[str, Any], decoded),
    )


def _body(
    report: ReliabilityVerificationReport, **changes: object
) -> dict[str, object]:
    """Create one bounded review statement request without actor identity fields."""
    values: dict[str, object] = {
        "schema_version": "review-statement-input.v1",
        "candidate_digest": report.candidate_digest,
        "report_digest": report.digest,
        "category": "observation",
        "statement": "The evidence is inspectable; human judgment remains separate.",
        "finding_refs": ["retrieval-evidence"],
        "limitation": "Not an approval.",
        "scope": "candidate review",
        "supersedes_digest": None,
    }
    values.update(changes)
    return values


def test_review_api_requires_authentication_and_operation_authorization(
    tmp_path: Path,
) -> None:
    """Fail closed before exposing or mutating review statements."""
    application, record_id, report = _secured_app(tmp_path)
    status, _, payload = _request(
        application,
        f"/api/v1/claims/{record_id}/reviews",
        method="POST",
        body=_body(report),
        authenticated=False,
        if_match=report.digest,
        idempotency_key="request-1",
    )
    assert status == "401 Unauthorized"
    assert payload["error"]["code"] == "AUTHENTICATION_REQUIRED"

    denied, denied_id, denied_report = _secured_app(
        tmp_path / "denied", authorize_write=False
    )
    status, _, payload = _request(
        denied,
        f"/api/v1/claims/{denied_id}/reviews",
        method="POST",
        body=_body(denied_report),
        if_match=denied_report.digest,
        idempotency_key="request-1",
    )
    assert status == "403 Forbidden"
    assert payload["error"]["code"] == "AUTHORIZATION_DENIED"


def test_review_write_requires_origin_csrf_and_exact_report_basis(
    tmp_path: Path,
) -> None:
    """Reject cross-origin, forged-CSRF, and stale-candidate writes."""
    application, record_id, report = _secured_app(tmp_path)
    path = f"/api/v1/claims/{record_id}/reviews"

    status, _, payload = _request(
        application,
        path,
        method="POST",
        body=_body(report),
        origin="https://evil.example",
        if_match=report.digest,
        idempotency_key="request-origin",
    )
    assert status == "403 Forbidden"
    assert payload["error"]["code"] == "ORIGIN_DENIED"

    status, _, payload = _request(
        application,
        path,
        method="POST",
        body=_body(report),
        csrf="wrong",
        if_match=report.digest,
        idempotency_key="request-csrf",
    )
    assert status == "403 Forbidden"
    assert payload["error"]["code"] == "CSRF_REJECTED"

    status, _, payload = _request(
        application,
        path,
        method="POST",
        body=_body(report),
        if_match="0" * 64,
        idempotency_key="request-stale",
    )
    assert status == "409 Conflict"
    assert payload["error"]["code"] == "STALE_REVIEW_BASIS"

    status, _, payload = _request(
        application,
        path,
        method="POST",
        body=_body(report, candidate_digest="0" * 64),
        if_match=report.digest,
        idempotency_key="request-candidate",
    )
    assert status == "409 Conflict"
    assert payload["error"]["code"] == "STALE_REVIEW_BASIS"


def test_review_write_uses_server_actor_and_never_creates_approval(
    tmp_path: Path,
) -> None:
    """Ignore client actor claims and keep free-text approval wording non-authoritative."""
    events: list[SecurityEvent] = []
    application, record_id, report = _secured_app(tmp_path, events=events)
    body = _body(report, statement="approved", category="review_complete")
    body["actor_identity_ref"] = "forged:client"
    body["actor_role"] = "release-approver"

    status, headers, payload = _request(
        application,
        f"/api/v1/claims/{record_id}/reviews",
        method="POST",
        body=body,
        if_match=report.digest,
        idempotency_key="request-1",
    )

    assert status == "201 Created"
    assert headers["ETag"] == f'"{payload["review"]["digest"]}"'
    assert payload["approval_created"] is False
    assert payload["review"]["actor_identity_ref"] == "reviewer:alice"
    assert payload["review"]["actor_role"] == "reliability-reviewer"
    assert payload["review"]["statement"] == "approved"
    assert payload["review"]["category"] == "review_complete"
    assert events[-1].operation == "review:write"


def test_review_write_is_idempotent_but_changed_replay_conflicts(
    tmp_path: Path,
) -> None:
    """Return the original statement for an exact retry and reject changed reuse."""
    application, record_id, report = _secured_app(tmp_path)
    path = f"/api/v1/claims/{record_id}/reviews"
    kwargs = {
        "method": "POST",
        "body": _body(report),
        "if_match": report.digest,
        "idempotency_key": "request-1",
    }
    first_status, _, first = _request(application, path, **kwargs)
    replay_status, _, replay = _request(application, path, **kwargs)

    assert first_status == "201 Created"
    assert replay_status == "200 OK"
    assert replay["created"] is False
    assert replay["review"]["digest"] == first["review"]["digest"]

    changed_status, _, changed = _request(
        application,
        path,
        method="POST",
        body=_body(report, statement="different"),
        if_match=report.digest,
        idempotency_key="request-1",
    )
    assert changed_status == "409 Conflict"
    assert changed["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_review_thread_read_is_exact_basis_and_conditional(tmp_path: Path) -> None:
    """Expose only immutable statements bound to the requested report digest."""
    application, record_id, report = _secured_app(tmp_path)
    path = f"/api/v1/claims/{record_id}/reviews"
    _request(
        application,
        path,
        method="POST",
        body=_body(report),
        if_match=report.digest,
        idempotency_key="request-1",
    )

    status, headers, payload = _request(application, path)
    assert status == "200 OK"
    assert payload["schema_version"] == "review-thread.v1"
    assert payload["target"]["report_digest"] == report.digest
    assert len(payload["items"]) == 1
    assert "not HumanApprovalContract" in payload["limitations"][1]

    environ_etag = headers["ETag"]
    raw = b""
    captured: dict[str, object] = {}

    def start_response(value: str, response_headers: list[tuple[str, str]]) -> None:
        captured["status"] = value
        captured["headers"] = response_headers

    environ = cast(
        WSGIEnvironment,
        {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": path,
            "CONTENT_LENGTH": "0",
            "wsgi.input": io.BytesIO(raw),
            "wsgi.url_scheme": "http",
            "HTTP_AUTHORIZATION": "Bearer test-token",
            "HTTP_IF_NONE_MATCH": environ_etag,
        },
    )
    response = b"".join(application(environ, start_response))
    assert captured["status"] == "304 Not Modified"
    assert response == b""


def test_review_capabilities_expose_statement_write_but_not_approval_write(
    tmp_path: Path,
) -> None:
    """Keep the newly available review operation separate from approval authority."""
    application, _, _ = _secured_app(tmp_path)
    status, _, payload = _request(application, "/api/v1/review-capabilities")

    assert status == "200 OK"
    assert payload["features"] == {
        "review_read": True,
        "review_write": True,
        "approval_read": False,
        "approval_write": False,
        "approval_revoke": False,
        "approval_supersede": False,
    }
    assert payload["actor"] == {
        "identity_ref": "reviewer:alice",
        "role": "reliability-reviewer",
    }


def test_review_config_rejects_non_origin_urls(tmp_path: Path) -> None:
    """Accept only canonical scheme/authority origins, never path-bearing URLs."""
    with pytest.raises(ValueError, match="origins"):
        ReviewApiConfig(
            tmp_path / "workspace",
            tmp_path / "reviews.jsonl",
            ("https://example.test/review",),
        )

    config = ReviewApiConfig(
        tmp_path / "workspace",
        tmp_path / "reviews.jsonl",
        ("HTTPS://EXAMPLE.TEST/",),
    )
    assert config.allowed_origins == ("https://example.test",)


def test_review_health_can_be_explicitly_public_without_exposing_review_data(
    tmp_path: Path,
) -> None:
    """Expose only a bounded service health response when the host allows that path."""
    application, _, _ = _secured_app(tmp_path, public_health=True)
    status, _, payload = _request(
        application,
        "/health",
        authenticated=False,
    )

    assert status == "200 OK"
    assert payload == {
        "approval_write": False,
        "service": "human-review",
        "statewake_version": __version__,
        "status": "ok",
    }


def _approval_body(
    report: ReliabilityVerificationReport,
    **changes: object,
) -> dict[str, object]:
    """Create one basis-bound human-approval request without authority fields."""
    values: dict[str, object] = {
        "schema_version": "human-approval-input.v1",
        "candidate_digest": report.candidate_digest,
        "report_digest": report.digest,
        "reason": "Reviewed the bounded evidence and approve the configured action.",
        "confirmed": True,
    }
    values.update(changes)
    return values


def _approval_lifecycle_body(
    report: ReliabilityVerificationReport,
    **changes: object,
) -> dict[str, object]:
    """Create one basis-bound lifecycle request without client-owned authority."""
    values: dict[str, object] = {
        "schema_version": "human-approval-lifecycle-input.v1",
        "candidate_digest": report.candidate_digest,
        "report_digest": report.digest,
        "reason": "Human reviewer intentionally changes the approval lifecycle.",
        "confirmed": True,
    }
    values.update(changes)
    return values


def test_approval_capability_is_explicit_and_server_scoped(tmp_path: Path) -> None:
    """Advertise approval only when a trusted server authority is configured."""
    application, _, _ = _secured_app(tmp_path, approval_enabled=True)
    status, _, payload = _request(application, "/api/v1/review-capabilities")

    assert status == "200 OK"
    assert payload["features"]["approval_read"] is True
    assert payload["features"]["approval_write"] is True
    assert payload["features"]["approval_revoke"] is True
    assert payload["features"]["approval_supersede"] is True
    assert payload["approval"] == {
        "configured": True,
        "note": (
            "Action and scope are resolved server-side for each exact report basis; "
            "the browser cannot supply approval authority."
        ),
    }


def test_human_approval_writes_canonical_contract_without_mutating_report(
    tmp_path: Path,
) -> None:
    """Persist HumanApprovalContract evidence while leaving machine/report state immutable."""
    application, record_id, report = _secured_app(tmp_path, approval_enabled=True)
    path = f"/api/v1/claims/{record_id}/approvals"
    body = _approval_body(report)
    body["actor_identity_ref"] = "forged:browser"
    body["approval_action"] = "publish-everything"
    body["scope"] = "global"

    status, headers, payload = _request(
        application,
        path,
        method="POST",
        body=body,
        if_match=report.digest,
        idempotency_key="approval-1",
    )

    assert status == "201 Created"
    contract = payload["approval"]["contract"]
    assert contract["contract_type"] == "human_approval"
    assert contract["actor_identity_ref"] == "reviewer:alice"
    assert contract["role"] == "reliability-reviewer"
    assert contract["producer_id"] == "statewake.test.approver"
    assert contract["run_id"] == "run-1"
    assert contract["approval_action"] == "approve-release-evidence"
    assert contract["scope"] == "candidate release evidence"
    assert contract["approval_basis_digest"] == report.digest
    assert contract["metadata"]["candidate_digest"] == report.candidate_digest
    assert contract["metadata"]["target_record_id"] == record_id
    assert payload["effects"] == {
        "verification_report_mutated": False,
        "machine_decision_changed": False,
        "release_published": False,
        "side_effect_authorized_outside_scope": False,
    }
    assert headers["ETag"] == f'"{payload["approval"]["receipt"]["receipt_digest"]}"'

    status, _, thread = _request(application, path)
    assert status == "200 OK"
    assert thread["schema_version"] == "human-approval-thread.v1"
    assert thread["authority"] == {
        "approval_action": "approve-release-evidence",
        "scope": "candidate release evidence",
    }
    assert len(thread["items"]) == 1
    assert thread["items"][0]["contract"] == contract
    assert thread["items"][0]["lifecycle"]["status"] == "active"
    assert thread["active_approval_receipt_ids"] == [
        payload["approval"]["receipt"]["receipt_id"]
    ]


def test_human_approval_is_idempotent_and_rejects_changed_replay(
    tmp_path: Path,
) -> None:
    """Collapse exact retries and reject changed reuse of an approval idempotency key."""
    application, record_id, report = _secured_app(tmp_path, approval_enabled=True)
    path = f"/api/v1/claims/{record_id}/approvals"
    kwargs = {
        "method": "POST",
        "body": _approval_body(report),
        "if_match": report.digest,
        "idempotency_key": "approval-1",
    }
    first_status, _, first = _request(application, path, **kwargs)
    replay_status, _, replay = _request(application, path, **kwargs)

    assert first_status == "201 Created"
    assert replay_status == "200 OK"
    assert replay["created"] is False
    assert (
        replay["approval"]["receipt"]["receipt_id"]
        == first["approval"]["receipt"]["receipt_id"]
    )

    changed_status, _, changed = _request(
        application,
        path,
        method="POST",
        body=_approval_body(report, reason="Changed approval rationale"),
        if_match=report.digest,
        idempotency_key="approval-1",
    )
    assert changed_status == "409 Conflict"
    assert changed["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_human_approval_rejects_duplicate_authority_and_stale_basis(
    tmp_path: Path,
) -> None:
    """Prevent contradictory duplicates and stale approval from another report basis."""
    application, record_id, report = _secured_app(tmp_path, approval_enabled=True)
    path = f"/api/v1/claims/{record_id}/approvals"
    _request(
        application,
        path,
        method="POST",
        body=_approval_body(report),
        if_match=report.digest,
        idempotency_key="approval-1",
    )

    duplicate_status, _, duplicate = _request(
        application,
        path,
        method="POST",
        body=_approval_body(report, reason="Another reason"),
        if_match=report.digest,
        idempotency_key="approval-2",
    )
    assert duplicate_status == "409 Conflict"
    assert duplicate["error"]["code"] == "APPROVAL_ALREADY_RECORDED"

    stale_status, _, stale = _request(
        application,
        path,
        method="POST",
        body=_approval_body(report),
        if_match="0" * 64,
        idempotency_key="approval-stale",
    )
    assert stale_status == "409 Conflict"
    assert stale["error"]["code"] == "STALE_REVIEW_BASIS"


def test_human_approval_requires_explicit_confirmation_and_required_status(
    tmp_path: Path,
) -> None:
    """Never create approval from an unconfirmed request or non-approval report."""
    application, record_id, report = _secured_app(tmp_path, approval_enabled=True)
    path = f"/api/v1/claims/{record_id}/approvals"
    status, _, payload = _request(
        application,
        path,
        method="POST",
        body=_approval_body(report, confirmed=False),
        if_match=report.digest,
        idempotency_key="approval-1",
    )
    assert status == "422 Unprocessable Entity"
    assert payload["error"]["code"] == "INVALID_HUMAN_REVIEW_REQUEST"

    root = tmp_path / "not-required"
    workspace = StateWakeWorkspace.open(root / "workspace")
    not_required = _report(
        approval_status="not-approval",
        human_decisions_required=(),
    )
    record = workspace.ingest(
        render_json_report(not_required).encode("utf-8"),
        producer_type="statewake-verification-report",
        producer_id="statewake.test",
        source_ref="report.json",
        source_event_id="report-1",
        run_id="run-1",
        captured_at=datetime(2026, 9, 27, tzinfo=UTC),
        metadata={"candidate_identity": not_required.candidate_identity},
    )
    workspace.verify(record)
    workspace.close()

    actor = ReviewActor("reviewer:alice", "reliability-reviewer")
    deployment = DeploymentSecurityConfig(
        authenticate=lambda _environ: actor,
        authorize=lambda _principal, _operation, _environ: True,
        require_https=False,
    )
    app = create_review_application(
        ReviewApiConfig(
            root / "workspace",
            root / "reviews.jsonl",
            ("http://localhost:3000",),
        ),
        ReviewApiSecurity(
            deployment,
            lambda _principal: actor,
            lambda _principal, token, _environ: token == "csrf-token",
            lambda _principal, _report, _source: ApprovalAuthority(
                "statewake.test.approver",
                "approve-release-evidence",
                "candidate release evidence",
            ),
        ),
    )
    status, _, payload = _request(
        app,
        f"/api/v1/claims/{record.record_id}/approvals",
        method="POST",
        body=_approval_body(not_required),
        if_match=not_required.digest,
        idempotency_key="approval-2",
    )
    assert status == "409 Conflict"
    assert payload["error"]["code"] == "APPROVAL_NOT_REQUIRED"


def test_human_approval_revocation_is_canonical_idempotent_and_visible(
    tmp_path: Path,
) -> None:
    """Revoke an active approval without mutating or deleting its historical evidence."""
    events: list[SecurityEvent] = []
    application, record_id, report = _secured_app(
        tmp_path, approval_enabled=True, events=events
    )
    approvals_path = f"/api/v1/claims/{record_id}/approvals"
    _, _, approved = _request(
        application,
        approvals_path,
        method="POST",
        body=_approval_body(report),
        if_match=report.digest,
        idempotency_key="approval-1",
    )
    approval_receipt_id = approved["approval"]["receipt"]["receipt_id"]
    revoke_path = f"{approvals_path}/{approval_receipt_id}/revoke"
    kwargs = {
        "method": "POST",
        "body": _approval_lifecycle_body(report),
        "if_match": report.digest,
        "idempotency_key": "revocation-1",
    }

    status, _, revoked = _request(application, revoke_path, **kwargs)
    replay_status, _, replay = _request(application, revoke_path, **kwargs)

    assert status == "201 Created"
    assert replay_status == "200 OK"
    assert revoked["schema_version"] == "human-approval-lifecycle-result.v1"
    assert revoked["operation"] == "revoke"
    assert revoked["approval"] is None
    assert (
        revoked["revocation"]["contract"]["target_approval_receipt_id"]
        == approval_receipt_id
    )
    assert replay["created"] is False
    assert (
        replay["revocation"]["receipt"]["receipt_id"]
        == revoked["revocation"]["receipt"]["receipt_id"]
    )
    assert events[-1].operation == "approval:revoke"

    thread_status, _, thread = _request(application, approvals_path)
    assert thread_status == "200 OK"
    assert thread["items"][0]["lifecycle"]["status"] == "revoked"
    assert thread["items"][0]["lifecycle"]["revocation"]["contract"]["reason"]
    assert thread["active_approval_receipt_ids"] == []


def test_human_approval_supersession_appends_replacement_and_deactivates_predecessor(
    tmp_path: Path,
) -> None:
    """Supersede one active approval while retaining the complete predecessor chain."""
    application, record_id, report = _secured_app(tmp_path, approval_enabled=True)
    approvals_path = f"/api/v1/claims/{record_id}/approvals"
    _, _, approved = _request(
        application,
        approvals_path,
        method="POST",
        body=_approval_body(report),
        if_match=report.digest,
        idempotency_key="approval-1",
    )
    old_id = approved["approval"]["receipt"]["receipt_id"]
    supersede_path = f"{approvals_path}/{old_id}/supersede"

    status, _, superseded = _request(
        application,
        supersede_path,
        method="POST",
        body=_approval_lifecycle_body(
            report, reason="Replacement approval records the corrected human rationale."
        ),
        if_match=report.digest,
        idempotency_key="approval-2",
    )

    assert status == "201 Created"
    assert superseded["operation"] == "supersede"
    replacement = superseded["approval"]
    assert (
        replacement["contract"]["metadata"]["supersedes_approval_receipt_id"] == old_id
    )
    replacement_id = replacement["receipt"]["receipt_id"]

    _, _, thread = _request(application, approvals_path)
    items = {item["receipt"]["receipt_id"]: item for item in thread["items"]}
    assert items[old_id]["lifecycle"]["status"] == "superseded"
    assert items[old_id]["lifecycle"]["superseded_by_receipt_id"] == replacement_id
    assert items[replacement_id]["lifecycle"]["status"] == "active"
    assert thread["active_approval_receipt_ids"] == [replacement_id]

    conflict_status, _, conflict = _request(
        application,
        f"{approvals_path}/{old_id}/revoke",
        method="POST",
        body=_approval_lifecycle_body(report),
        if_match=report.digest,
        idempotency_key="revocation-after-supersession",
    )
    assert conflict_status == "409 Conflict"
    assert conflict["error"]["code"] == "APPROVAL_LIFECYCLE_CONFLICT"


def test_human_approval_lifecycle_requires_exact_basis_and_separate_authorization(
    tmp_path: Path,
) -> None:
    """Enforce security, confirmation, and exact target identity on lifecycle writes."""
    application, record_id, report = _secured_app(tmp_path, approval_enabled=True)
    approvals_path = f"/api/v1/claims/{record_id}/approvals"
    _, _, approved = _request(
        application,
        approvals_path,
        method="POST",
        body=_approval_body(report),
        if_match=report.digest,
        idempotency_key="approval-1",
    )
    approval_id = approved["approval"]["receipt"]["receipt_id"]
    revoke_path = f"{approvals_path}/{approval_id}/revoke"

    stale_status, _, stale = _request(
        application,
        revoke_path,
        method="POST",
        body=_approval_lifecycle_body(report),
        if_match="0" * 64,
        idempotency_key="revocation-stale",
    )
    assert stale_status == "409 Conflict"
    assert stale["error"]["code"] == "STALE_REVIEW_BASIS"

    unconfirmed_status, _, unconfirmed = _request(
        application,
        revoke_path,
        method="POST",
        body=_approval_lifecycle_body(report, confirmed=False),
        if_match=report.digest,
        idempotency_key="revocation-unconfirmed",
    )
    assert unconfirmed_status == "422 Unprocessable Entity"
    assert unconfirmed["error"]["code"] == "INVALID_HUMAN_REVIEW_REQUEST"

    missing_status, _, missing = _request(
        application,
        f"{approvals_path}/{('f' * 64)}/revoke",
        method="POST",
        body=_approval_lifecycle_body(report),
        if_match=report.digest,
        idempotency_key="revocation-missing",
    )
    assert missing_status == "409 Conflict"
    assert missing["error"]["code"] == "APPROVAL_LIFECYCLE_TARGET_INVALID"

    denied, denied_id, denied_report = _secured_app(
        tmp_path / "denied-lifecycle",
        approval_enabled=True,
        authorize_write=False,
    )
    denied_status, _, denied_payload = _request(
        denied,
        f"/api/v1/claims/{denied_id}/approvals/{('e' * 64)}/revoke",
        method="POST",
        body=_approval_lifecycle_body(denied_report),
        if_match=denied_report.digest,
        idempotency_key="revocation-denied",
    )
    assert denied_status == "403 Forbidden"
    assert denied_payload["error"]["code"] == "AUTHORIZATION_DENIED"


def test_capabilities_reflect_principal_write_authorization(tmp_path: Path) -> None:
    """Never advertise review/approval writes the current principal cannot perform."""
    application, _, _ = _secured_app(
        tmp_path,
        authorize_write=False,
        approval_enabled=True,
    )
    status, _, payload = _request(application, "/api/v1/review-capabilities")

    assert status == "200 OK"
    assert payload["features"] == {
        "review_read": True,
        "review_write": False,
        "approval_read": True,
        "approval_write": False,
        "approval_revoke": False,
        "approval_supersede": False,
    }
    assert payload["approval"]["configured"] is True
