# Identity-bound access and authorization policy investigation

StateWake's authorization domain is deliberately small and deny-by-default. It consumes an already authenticated `Principal`, checks explicit resource scope, evaluates role/operation/resource-state grants, and returns an explainable `AuthorizationDecision`.

StateWake is **not** an identity provider or IAM database. The current repository does not persist a canonical principal/grant store. The investigation surface therefore reads one explicitly configured context artifact:

```text
STATEWAKE_UI_AUTHORIZATION_CONTEXT=<authorization-context.v1 JSON>
```

The artifact contains only serialized forms of existing domain contracts:

```text
Principal
AuthorizationPolicy / AuthorizationGrant
AuthorizationRequest
optional recorded AuthorizationDecision
```

The reader rejects symlink traversal, malformed UTF-8/JSON, unsupported fields, scalar coercion, invalid enums/timestamps, and byte-limit overflow. It reconstructs the existing domain objects and calls `AuthorizationPolicy.authorize(...)`. If a recorded decision is present, it must match the replay exactly or the source is rejected.

The browser never receives raw principal IDs, resource-domain IDs, or resource IDs. Those identities are projected only as SHA-256 digests. Roles, protected operation, resource state, grant rules, replay conditions, and the final allow/deny reason remain visible because they are needed to explain the StateWake policy decision.

The surface explicitly does **not** evaluate caller authentication, session validity, MFA, TLS, tenant isolation, or broader business authorization. An `allowed` StateWake result means only that the supplied authenticated principal satisfied the configured StateWake resource/operation/state policy for that exact request.
