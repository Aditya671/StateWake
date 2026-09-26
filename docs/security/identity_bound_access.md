# Tier 11 — Identity-Bound Access & Least Privilege

## Scope

This document specifies Tier 11 authorization controls, evidence requirements, and verification criteria. Independent certification and publication decisions remain separate governance activities.

## Objective

Tier 11 defines the StateWake-side authorization contract for security-sensitive operations without implementing an identity provider, enterprise directory, password store, SSO system, MFA service, or other external identity infrastructure.

## Existing boundary reused

`statewake.adapters.deployment_security` already requires the host/application boundary to authenticate a principal and authorize verification requests before the existing read-only verification application is reached. Tier 11 does not replace that boundary.

Tier 11 adds explicit StateWake semantics for:

```text
principal → operation → resource domain → resource → resource state → decision
```

## Actor model

The authenticated principal is represented only by the attributes needed by StateWake authorization:

- stable principal identity;
- explicit roles;
- explicit resource scopes;
- active/revoked lifecycle state;
- optional authorization expiry.

Identity-provider implementation remains outside StateWake.

## Operations

The contract distinguishes:

`READ`, `INGEST`, `VERIFY`, `TRANSITION`, `RECONCILE`, `RECOVER`, `ATTEST`, `DELETE`, `RETAIN`, `ADMINISTER_TRUST`, and `ADMINISTER_KEYS`.

No operation inherits permission merely because another operation is allowed.

## Least privilege

A grant explicitly binds:

```text
role + operation + allowed resource state
```

Resource access is separately scoped to an explicit resource domain and resource identifier. No wildcard resource grant or broad administrator role is created by default.

## State-aware authorization

Authorization succeeds only when all of the following hold:

```text
principal active
AND resource in principal scope
AND operation granted to one of principal roles
AND current resource state is allowed by that grant
```

Authentication alone never implies permission.

## Failure semantics

```text
revoked principal        → deny
expired principal        → deny
wrong resource/domain    → deny
operation absent         → deny
state not allowed        → deny
all conditions satisfied → allow
```

Authorization uncertainty is never interpreted as permission.

## Separation of duties

The contract does not require one principal to own every function. Sensitive operations remain separately grantable, allowing deployments to assign verification, recovery, attestation, trust administration, and key administration to distinct principals or roles.

## State of truth

Authorization is a boundary decision. It does not mutate reliability state, evidence, provenance, attestation state, or trust state.

## Exit evidence

Tier 11 is considered satisfied when tests demonstrate authenticated-but-unauthorized access, operation separation, resource and cross-domain scoping, recovery/attestation denial, invalid-state denial, role confusion rejection, revocation, expiry, and allow-on-all-required-conditions behavior.
