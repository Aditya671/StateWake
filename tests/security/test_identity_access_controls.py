"""Regression coverage for Tier 11 identity-bound access and least privilege."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from statewake.domain.access_control import (
    AuthorizationGrant,
    AuthorizationOperation,
    AuthorizationPolicy,
    AuthorizationRequest,
    Principal,
    PrincipalStatus,
)

NOW = datetime(2026, 9, 16, 5, 0, tzinfo=UTC)


def _request(
    operation: AuthorizationOperation,
    *,
    resource_domain: str = "team-a",
    resource_id: str = "evidence-1",
    resource_state: str = "verified",
) -> AuthorizationRequest:
    return AuthorizationRequest(
        operation=operation,
        resource_domain=resource_domain,
        resource_id=resource_id,
        resource_state=resource_state,
        requested_at=NOW,
    )


def _policy() -> AuthorizationPolicy:
    return AuthorizationPolicy(
        grants=(
            AuthorizationGrant("reader", AuthorizationOperation.READ, ("verified",)),
            AuthorizationGrant("reader", AuthorizationOperation.VERIFY, ("verified",)),
            AuthorizationGrant("writer", AuthorizationOperation.INGEST, ("pending",)),
            AuthorizationGrant(
                "recovery-operator", AuthorizationOperation.RECOVER, ("degraded",)
            ),
            AuthorizationGrant(
                "attestor", AuthorizationOperation.ATTEST, ("reliable",)
            ),
        )
    )


def test_authenticated_but_unauthorized() -> None:
    principal = Principal(
        "alice", roles=("reader",), resource_scopes={"team-a": ("evidence-1",)}
    )
    decision = _policy().authorize(
        principal, _request(AuthorizationOperation.RECOVER, resource_state="degraded")
    )
    assert not decision.allowed
    assert decision.reason == "operation_not_authorized"


def test_read_does_not_imply_write() -> None:
    principal = Principal(
        "alice", roles=("reader",), resource_scopes={"team-a": ("evidence-1",)}
    )
    decision = _policy().authorize(
        principal, _request(AuthorizationOperation.INGEST, resource_state="pending")
    )
    assert not decision.allowed
    assert decision.reason == "operation_not_authorized"


def test_wrong_resource_is_denied() -> None:
    principal = Principal(
        "alice", roles=("reader",), resource_scopes={"team-a": ("evidence-1",)}
    )
    decision = _policy().authorize(
        principal, _request(AuthorizationOperation.READ, resource_id="evidence-2")
    )
    assert not decision.allowed
    assert decision.reason == "resource_scope_denied"


def test_unauthorized_recovery_is_denied() -> None:
    principal = Principal(
        "alice", roles=("reader",), resource_scopes={"team-a": ("evidence-1",)}
    )
    decision = _policy().authorize(
        principal, _request(AuthorizationOperation.RECOVER, resource_state="degraded")
    )
    assert not decision.allowed


def test_unauthorized_attestation_is_denied() -> None:
    principal = Principal(
        "alice", roles=("reader",), resource_scopes={"team-a": ("evidence-1",)}
    )
    decision = _policy().authorize(
        principal, _request(AuthorizationOperation.ATTEST, resource_state="reliable")
    )
    assert not decision.allowed


def test_invalid_resource_state_is_denied() -> None:
    principal = Principal(
        "alice",
        roles=("recovery-operator",),
        resource_scopes={"team-a": ("evidence-1",)},
    )
    decision = _policy().authorize(
        principal, _request(AuthorizationOperation.RECOVER, resource_state="reliable")
    )
    assert not decision.allowed
    assert decision.reason == "operation_not_authorized"


def test_role_confusion_is_denied() -> None:
    principal = Principal(
        "alice", roles=("reader",), resource_scopes={"team-a": ("evidence-1",)}
    )
    decision = _policy().authorize(
        principal, _request(AuthorizationOperation.INGEST, resource_state="pending")
    )
    assert not decision.allowed


def test_revoked_principal_is_denied() -> None:
    principal = Principal(
        "alice",
        roles=("reader",),
        resource_scopes={"team-a": ("evidence-1",)},
        status=PrincipalStatus.REVOKED,
    )
    decision = _policy().authorize(principal, _request(AuthorizationOperation.READ))
    assert not decision.allowed
    assert decision.reason == "principal_revoked"


def test_expired_principal_is_denied() -> None:
    principal = Principal(
        "alice",
        roles=("reader",),
        resource_scopes={"team-a": ("evidence-1",)},
        expires_at=NOW - timedelta(seconds=1),
    )
    decision = _policy().authorize(principal, _request(AuthorizationOperation.READ))
    assert not decision.allowed
    assert decision.reason == "authorization_expired"


def test_cross_domain_access_is_denied() -> None:
    principal = Principal(
        "alice", roles=("reader",), resource_scopes={"team-a": ("evidence-1",)}
    )
    decision = _policy().authorize(
        principal,
        _request(
            AuthorizationOperation.READ,
            resource_domain="team-b",
            resource_id="evidence-1",
        ),
    )
    assert not decision.allowed
    assert decision.reason == "resource_scope_denied"


def test_all_required_conditions_allow() -> None:
    principal = Principal(
        "bob", roles=("reader",), resource_scopes={"team-a": ("evidence-1",)}
    )
    decision = _policy().authorize(principal, _request(AuthorizationOperation.READ))
    assert decision.allowed
    assert decision.matched_role == "reader"


def test_separate_sensitive_roles_remain_distinct() -> None:
    principal = Principal(
        "carol",
        roles=("recovery-operator",),
        resource_scopes={"team-a": ("evidence-1",)},
    )
    recovery = _policy().authorize(
        principal, _request(AuthorizationOperation.RECOVER, resource_state="degraded")
    )
    attestation = _policy().authorize(
        principal, _request(AuthorizationOperation.ATTEST, resource_state="reliable")
    )
    assert recovery.allowed
    assert not attestation.allowed
