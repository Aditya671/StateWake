"""Identity-bound authorization contracts for StateWake operations."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class AuthorizationOperation(StrEnum):
    """StateWake operations that require explicit authorization."""

    READ = "READ"
    INGEST = "INGEST"
    VERIFY = "VERIFY"
    TRANSITION = "TRANSITION"
    RECONCILE = "RECONCILE"
    RECOVER = "RECOVER"
    ATTEST = "ATTEST"
    DELETE = "DELETE"
    RETAIN = "RETAIN"
    ADMINISTER_TRUST = "ADMINISTER_TRUST"
    ADMINISTER_KEYS = "ADMINISTER_KEYS"


class PrincipalStatus(StrEnum):
    """Lifecycle status of an externally authenticated principal."""

    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated principal attributes consumed by StateWake authorization."""

    principal_id: str
    roles: tuple[str, ...] = ()
    resource_scopes: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    status: PrincipalStatus = PrincipalStatus.ACTIVE
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        """Reject ambiguous or empty principal attributes."""
        if not self.principal_id.strip():
            raise ValueError("principal_id must not be empty.")
        if any(not role.strip() for role in self.roles):
            raise ValueError("roles must not contain blank values.")
        if any(not domain.strip() for domain in self.resource_scopes):
            raise ValueError("resource-scope domains must not be blank.")
        if any(
            any(not resource.strip() for resource in resources)
            for resources in self.resource_scopes.values()
        ):
            raise ValueError("resource scopes must not contain blank values.")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ValueError("principal expiry must be timezone-aware.")

    def active_at(self, when: datetime) -> bool:
        """Return whether this principal is active at the supplied instant."""
        if when.tzinfo is None:
            raise ValueError("authorization timestamps must be timezone-aware.")
        if self.status is PrincipalStatus.REVOKED:
            return False
        if self.expires_at is None:
            return True
        return when.astimezone(UTC) < self.expires_at.astimezone(UTC)

    def can_access_resource(self, domain: str, resource_id: str) -> bool:
        """Return whether the principal has explicit scope for one resource."""
        allowed = self.resource_scopes.get(domain, ())
        return resource_id in allowed


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    """State-aware authorization context for one protected operation."""

    operation: AuthorizationOperation
    resource_domain: str
    resource_id: str
    resource_state: str
    requested_at: datetime

    def __post_init__(self) -> None:
        """Validate the resource and state context before policy evaluation."""
        for name in ("resource_domain", "resource_id", "resource_state"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be empty.")
        if self.requested_at.tzinfo is None:
            raise ValueError("requested_at must be timezone-aware.")


@dataclass(frozen=True, slots=True)
class AuthorizationGrant:
    """Least-privilege grant for one role, operation, and allowed state set."""

    role: str
    operation: AuthorizationOperation
    allowed_states: tuple[str, ...]

    def __post_init__(self) -> None:
        """Require explicit role and state grants."""
        if not self.role.strip():
            raise ValueError("grant role must not be empty.")
        if not self.allowed_states:
            raise ValueError("grant must contain at least one state.")
        if any(not state.strip() for state in self.allowed_states):
            raise ValueError("grant states must not contain blank values.")


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """Explainable allow/deny result for one authorization request."""

    allowed: bool
    principal_id: str
    operation: AuthorizationOperation
    resource_domain: str
    resource_id: str
    resource_state: str
    reason: str
    matched_role: str | None = None


@dataclass(frozen=True, slots=True)
class AuthorizationPolicy:
    """Explicit deny-by-default authorization policy."""

    grants: tuple[AuthorizationGrant, ...] = ()

    def authorize(
        self,
        principal: Principal,
        request: AuthorizationRequest,
    ) -> AuthorizationDecision:
        """Evaluate identity, resource, operation, and state independently."""
        when = request.requested_at
        if not principal.active_at(when):
            reason = (
                "principal_revoked"
                if principal.status is PrincipalStatus.REVOKED
                else "authorization_expired"
            )
            return _deny(principal, request, reason)

        if not principal.can_access_resource(
            request.resource_domain, request.resource_id
        ):
            return _deny(principal, request, "resource_scope_denied")

        for grant in self.grants:
            if grant.operation is not request.operation:
                continue
            if grant.role not in principal.roles:
                continue
            if request.resource_state not in grant.allowed_states:
                continue
            return AuthorizationDecision(
                allowed=True,
                principal_id=principal.principal_id,
                operation=request.operation,
                resource_domain=request.resource_domain,
                resource_id=request.resource_id,
                resource_state=request.resource_state,
                reason="authorized",
                matched_role=grant.role,
            )

        return _deny(principal, request, "operation_not_authorized")


def _deny(
    principal: Principal,
    request: AuthorizationRequest,
    reason: str,
) -> AuthorizationDecision:
    """Create a consistent deny result without exposing sensitive context."""
    return AuthorizationDecision(
        allowed=False,
        principal_id=principal.principal_id,
        operation=request.operation,
        resource_domain=request.resource_domain,
        resource_id=request.resource_id,
        resource_state=request.resource_state,
        reason=reason,
    )
