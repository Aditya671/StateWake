"""Strict read-side reconstruction of StateWake authorization policy context."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from statewake.domain.access_control import (
    AuthorizationDecision,
    AuthorizationGrant,
    AuthorizationOperation,
    AuthorizationPolicy,
    AuthorizationRequest,
    Principal,
    PrincipalStatus,
)

AUTHORIZATION_CONTEXT_SCHEMA_VERSION = "authorization-context.v1"


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    """One explicit authorization snapshot reconstructed from domain contracts."""

    principal: Principal
    policy: AuthorizationPolicy
    request: AuthorizationRequest
    decision: AuthorizationDecision
    recorded_decision_present: bool


def _read_object(path: Path, *, max_bytes: int) -> dict[str, Any]:
    """Read one bounded UTF-8 JSON object without following symlinks."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ValueError("authorization context path cannot traverse a symlink")
    with path.open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise OverflowError("authorization context exceeds configured byte limit")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("authorization context must be UTF-8") from exc
    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError("authorization context is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("authorization context must be a JSON object")
    return payload


def _keys(
    payload: dict[str, Any], *, allowed: set[str], required: set[str], name: str
) -> None:
    """Reject missing or unsupported fields for one strict JSON object."""
    extra = set(payload) - allowed
    missing = required - set(payload)
    if extra:
        raise ValueError(f"{name} contains unsupported fields: {sorted(extra)!r}")
    if missing:
        raise ValueError(f"{name} is missing required fields: {sorted(missing)!r}")


def _string(value: Any, name: str) -> str:
    """Return one non-empty string without scalar coercion."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _strings(value: Any, name: str) -> tuple[str, ...]:
    """Return one tuple of non-empty strings without coercion."""
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{name} must be an array of non-empty strings")
    return tuple(value)


def _timestamp(value: Any, name: str) -> datetime:
    """Parse one timezone-aware ISO timestamp."""
    text = _string(value, name)
    when = datetime.fromisoformat(text)
    if when.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return when


def _principal(payload: Any) -> Principal:
    """Parse a strict principal object into the existing domain contract."""
    if not isinstance(payload, dict):
        raise ValueError("principal must be an object")
    allowed = {"principal_id", "roles", "resource_scopes", "status", "expires_at"}
    required = {"principal_id", "roles", "resource_scopes", "status", "expires_at"}
    _keys(payload, allowed=allowed, required=required, name="principal")
    raw_scopes = payload["resource_scopes"]
    if not isinstance(raw_scopes, dict):
        raise ValueError("resource_scopes must be an object")
    scopes: dict[str, tuple[str, ...]] = {}
    for domain, resources in raw_scopes.items():
        domain_text = _string(domain, "resource scope domain")
        scopes[domain_text] = _strings(resources, f"resource scopes for {domain_text}")
    status_text = _string(payload["status"], "principal status")
    try:
        status = PrincipalStatus(status_text)
    except ValueError as exc:
        raise ValueError("unsupported principal status") from exc
    expires_raw = payload["expires_at"]
    if expires_raw is not None and not isinstance(expires_raw, str):
        raise ValueError("expires_at must be a string or null")
    expires = None if expires_raw is None else _timestamp(expires_raw, "expires_at")
    return Principal(
        principal_id=_string(payload["principal_id"], "principal_id"),
        roles=_strings(payload["roles"], "roles"),
        resource_scopes=scopes,
        status=status,
        expires_at=expires,
    )


def _policy(payload: Any) -> AuthorizationPolicy:
    """Parse strict least-privilege grants into the existing policy contract."""
    if not isinstance(payload, dict):
        raise ValueError("policy must be an object")
    _keys(payload, allowed={"grants"}, required={"grants"}, name="policy")
    raw_grants = payload["grants"]
    if not isinstance(raw_grants, list):
        raise ValueError("policy grants must be an array")
    grants: list[AuthorizationGrant] = []
    for index, raw in enumerate(raw_grants):
        if not isinstance(raw, dict):
            raise ValueError(f"grant {index} must be an object")
        _keys(
            raw,
            allowed={"role", "operation", "allowed_states"},
            required={"role", "operation", "allowed_states"},
            name=f"grant {index}",
        )
        operation_text = _string(raw["operation"], f"grant {index} operation")
        try:
            operation = AuthorizationOperation(operation_text)
        except ValueError as exc:
            raise ValueError(f"grant {index} has unsupported operation") from exc
        grants.append(
            AuthorizationGrant(
                role=_string(raw["role"], f"grant {index} role"),
                operation=operation,
                allowed_states=_strings(
                    raw["allowed_states"], f"grant {index} allowed_states"
                ),
            )
        )
    return AuthorizationPolicy(grants=tuple(grants))


def _request(payload: Any) -> AuthorizationRequest:
    """Parse one strict authorization request."""
    if not isinstance(payload, dict):
        raise ValueError("request must be an object")
    allowed = {
        "operation",
        "resource_domain",
        "resource_id",
        "resource_state",
        "requested_at",
    }
    _keys(payload, allowed=allowed, required=allowed, name="request")
    operation_text = _string(payload["operation"], "request operation")
    try:
        operation = AuthorizationOperation(operation_text)
    except ValueError as exc:
        raise ValueError("request has unsupported operation") from exc
    return AuthorizationRequest(
        operation=operation,
        resource_domain=_string(payload["resource_domain"], "resource_domain"),
        resource_id=_string(payload["resource_id"], "resource_id"),
        resource_state=_string(payload["resource_state"], "resource_state"),
        requested_at=_timestamp(payload["requested_at"], "requested_at"),
    )


def _recorded_decision(payload: Any) -> AuthorizationDecision:
    """Parse one optional recorded authorization decision strictly."""
    if not isinstance(payload, dict):
        raise ValueError("recorded_decision must be an object")
    allowed = {
        "allowed",
        "principal_id",
        "operation",
        "resource_domain",
        "resource_id",
        "resource_state",
        "reason",
        "matched_role",
    }
    _keys(payload, allowed=allowed, required=allowed, name="recorded_decision")
    if not isinstance(payload["allowed"], bool):
        raise ValueError("recorded_decision.allowed must be a boolean")
    matched_role = payload["matched_role"]
    if matched_role is not None and (
        not isinstance(matched_role, str) or not matched_role.strip()
    ):
        raise ValueError("recorded_decision.matched_role must be a string or null")
    operation_text = _string(payload["operation"], "recorded decision operation")
    try:
        operation = AuthorizationOperation(operation_text)
    except ValueError as exc:
        raise ValueError("recorded decision has unsupported operation") from exc
    return AuthorizationDecision(
        allowed=payload["allowed"],
        principal_id=_string(payload["principal_id"], "recorded principal_id"),
        operation=operation,
        resource_domain=_string(payload["resource_domain"], "recorded resource_domain"),
        resource_id=_string(payload["resource_id"], "recorded resource_id"),
        resource_state=_string(payload["resource_state"], "recorded resource_state"),
        reason=_string(payload["reason"], "recorded reason"),
        matched_role=matched_role,
    )


def _decision_dict(decision: AuthorizationDecision) -> dict[str, object]:
    """Return one stable semantic representation for replay comparison."""
    return {
        "allowed": decision.allowed,
        "principal_id": decision.principal_id,
        "operation": decision.operation.value,
        "resource_domain": decision.resource_domain,
        "resource_id": decision.resource_id,
        "resource_state": decision.resource_state,
        "reason": decision.reason,
        "matched_role": decision.matched_role,
    }


def load_authorization_context(path: Path, *, max_bytes: int) -> AuthorizationContext:
    """Load one explicit context and verify any recorded decision by policy replay."""
    payload = _read_object(path, max_bytes=max_bytes)
    allowed = {"schema_version", "principal", "policy", "request", "recorded_decision"}
    required = {"schema_version", "principal", "policy", "request"}
    _keys(payload, allowed=allowed, required=required, name="authorization context")
    if payload["schema_version"] != AUTHORIZATION_CONTEXT_SCHEMA_VERSION:
        raise ValueError("unsupported authorization context schema_version")
    principal = _principal(payload["principal"])
    policy = _policy(payload["policy"])
    request = _request(payload["request"])
    replayed = policy.authorize(principal, request)
    raw_recorded = payload.get("recorded_decision")
    if raw_recorded is not None:
        recorded = _recorded_decision(raw_recorded)
        if _decision_dict(recorded) != _decision_dict(replayed):
            raise ValueError(
                "recorded authorization decision does not match policy replay"
            )
        recorded_present = True
    else:
        recorded_present = False
    return AuthorizationContext(
        principal=principal,
        policy=policy,
        request=request,
        decision=replayed,
        recorded_decision_present=recorded_present,
    )
