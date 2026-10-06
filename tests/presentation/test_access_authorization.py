"""Presentation regressions for identity-bound authorization investigation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from statewake.domain.access_control import (
    AuthorizationGrant,
    AuthorizationOperation,
    AuthorizationPolicy,
    AuthorizationRequest,
    Principal,
)
from statewake.presentation.access_authorization import AccessAuthorizationProjection
from statewake.services.access_control_investigation_service import AuthorizationContext


def _mapping(value: object) -> dict[str, object]:
    """Narrow one JSON-like projection object for type-safe assertions."""
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def test_projection_hides_principal_and_resource_identities() -> None:
    principal = Principal(
        "SENSITIVE_PRINCIPAL",
        roles=("reader",),
        resource_scopes={"SENSITIVE_DOMAIN": ("SENSITIVE_RESOURCE",)},
    )
    policy = AuthorizationPolicy(
        grants=(
            AuthorizationGrant("reader", AuthorizationOperation.READ, ("verified",)),
        )
    )
    request = AuthorizationRequest(
        AuthorizationOperation.READ,
        "SENSITIVE_DOMAIN",
        "SENSITIVE_RESOURCE",
        "verified",
        datetime(2026, 9, 30, tzinfo=UTC),
    )
    decision = policy.authorize(principal, request)
    projection = AccessAuthorizationProjection(
        AuthorizationContext(principal, policy, request, decision, True)
    ).to_dict()
    rendered = repr(projection)
    assert "SENSITIVE_PRINCIPAL" not in rendered
    assert "SENSITIVE_DOMAIN" not in rendered
    assert "SENSITIVE_RESOURCE" not in rendered
    decision_payload = _mapping(projection["decision"])
    authorization_boundary = _mapping(projection["authorization_boundary"])
    assert decision_payload["allowed"] is True
    assert authorization_boundary["principal_authentication_evaluated"] is False


def test_projection_keeps_deny_reason_and_policy_replay_explicit() -> None:
    principal = Principal(
        "alice",
        roles=("reader",),
        resource_scopes={"team-a": ("evidence-1",)},
    )
    policy = AuthorizationPolicy(
        grants=(
            AuthorizationGrant("reader", AuthorizationOperation.READ, ("verified",)),
        )
    )
    request = AuthorizationRequest(
        AuthorizationOperation.RECOVER,
        "team-a",
        "evidence-1",
        "degraded",
        datetime(2026, 9, 30, tzinfo=UTC),
    )
    decision = policy.authorize(principal, request)
    payload = AccessAuthorizationProjection(
        AuthorizationContext(principal, policy, request, decision, False)
    ).to_dict()
    decision_payload = _mapping(payload["decision"])
    evaluation = _mapping(payload["evaluation"])
    assert decision_payload["allowed"] is False
    assert decision_payload["reason"] == "operation_not_authorized"
    assert evaluation["policy_replay_verified"] is True
    assert evaluation["recorded_decision_present"] is False
