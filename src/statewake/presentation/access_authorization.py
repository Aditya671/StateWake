"""Read-only identity-bound access and authorization policy investigation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from statewake.services.access_control_investigation_service import AuthorizationContext

ACCESS_AUTHORIZATION_SCHEMA_VERSION = "access-authorization-investigation.v1"


def _digest(value: str) -> str:
    """Return one stable privacy-safe SHA-256 identity digest."""
    return sha256(value.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class AccessAuthorizationProjection:
    """Privacy-safe projection over one explicitly configured authorization context."""

    context: AuthorizationContext

    def to_dict(self) -> dict[str, object]:
        """Render the deny-by-default decision without exposing identity/resource values."""
        principal = self.context.principal
        request = self.context.request
        decision = self.context.decision
        scope_rows = [
            {
                "resource_domain_digest": _digest(domain),
                "resource_id_digests": [_digest(item) for item in resources],
                "resource_count": len(resources),
            }
            for domain, resources in sorted(principal.resource_scopes.items())
        ]
        grants = [
            {
                "role": grant.role,
                "operation": grant.operation.value,
                "allowed_states": list(grant.allowed_states),
            }
            for grant in self.context.policy.grants
        ]
        request_scope_match = principal.can_access_resource(
            request.resource_domain, request.resource_id
        )
        matching_grants = [
            grant
            for grant in self.context.policy.grants
            if grant.role in principal.roles
            and grant.operation is request.operation
            and request.resource_state in grant.allowed_states
        ]
        return {
            "schema_version": ACCESS_AUTHORIZATION_SCHEMA_VERSION,
            "source": {
                "resource": "explicit-authorization-context-artifact",
                "configured": True,
                "source_path_exposed": False,
                "canonical_iam_store": False,
            },
            "principal": {
                "principal_id_digest": _digest(principal.principal_id),
                "principal_id_exposed": False,
                "status": principal.status.value,
                "roles": list(principal.roles),
                "expires_at": (
                    None
                    if principal.expires_at is None
                    else principal.expires_at.isoformat()
                ),
                "active_at_request": principal.active_at(request.requested_at),
                "resource_scope_domain_count": len(scope_rows),
                "resource_scope_resource_count": sum(
                    len(items) for items in principal.resource_scopes.values()
                ),
                "resource_scopes": scope_rows,
            },
            "request": {
                "operation": request.operation.value,
                "resource_domain_digest": _digest(request.resource_domain),
                "resource_id_digest": _digest(request.resource_id),
                "resource_identity_exposed": False,
                "resource_state": request.resource_state,
                "requested_at": request.requested_at.isoformat(),
            },
            "policy": {
                "deny_by_default": True,
                "grant_count": len(grants),
                "grants": grants,
            },
            "evaluation": {
                "principal_active": principal.active_at(request.requested_at),
                "resource_scope_match": request_scope_match,
                "matching_grant_count": len(matching_grants),
                "recorded_decision_present": self.context.recorded_decision_present,
                "recorded_decision_verified": self.context.recorded_decision_present,
                "policy_replay_verified": True,
            },
            "decision": {
                "allowed": decision.allowed,
                "reason": decision.reason,
                "matched_role": decision.matched_role,
                "operation": decision.operation.value,
                "resource_state": decision.resource_state,
                "principal_id_digest": _digest(decision.principal_id),
                "resource_domain_digest": _digest(decision.resource_domain),
                "resource_id_digest": _digest(decision.resource_id),
            },
            "authorization_boundary": {
                "principal_authentication_evaluated": False,
                "identity_provider": "external-host",
                "session_validity_evaluated": False,
                "mfa_evaluated": False,
                "tls_evaluated": False,
                "tenant_isolation_evaluated": False,
                "iam_provider": False,
                "business_authorization_inferred": False,
            },
            "limitations": [
                "This artifact is an explicit investigation input; StateWake does not persist a canonical IAM database.",
                "AuthorizationPolicy is deny-by-default but consumes an already authenticated external principal.",
                "Principal, resource-domain, and resource identities are represented only by SHA-256 digests in this view.",
                "A policy allow decision does not establish caller authentication, MFA, TLS, tenant isolation, or broader business authorization.",
            ],
        }
