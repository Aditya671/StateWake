# Security Audit & Deployment Assurance Investigation

StateWake exposes an optional **read-only deployment-security and runtime-containment investigation surface** over the canonical hash-linked `JsonlSecurityAuditStore` journal plus an explicitly emitted verification-service configuration snapshot.

This capability does not create a second security or containment subsystem. It reuses the existing `DeploymentSecurityConfig`, `SecurityEvent`, `SecurityAuditRecord`, `VerificationServiceConfig`, and `RuntimeContainmentLimits` authorities. Runtime configuration is shown only when the verification service itself emitted the snapshot; repository defaults are never presented as active deployment state.

## Configuration

Configure either or both evidence sources. To emit the effective verification-service runtime configuration:

```powershell
$env:STATEWAKE_VERIFICATION_RUNTIME_SNAPSHOT = "C:\path\to\runtime-containment.json"
python -m statewake.server
```

Point the read API at the resulting snapshot and/or an existing security audit journal:

```powershell
$env:STATEWAKE_UI_SECURITY_AUDIT = "C:\path\to\security-audit.jsonl"  # optional
$env:STATEWAKE_UI_RUNTIME_CONTAINMENT_SNAPSHOT = "C:\path\to\runtime-containment.json"  # optional
python -m statewake.read_api
```

At least one of the two sources must be configured for `/security-assurance` to be advertised.

The browser page is:

```text
/security-assurance
```

The API endpoint is:

```text
GET /api/v1/security-assurance
```

Optional exact filters:

```text
event
operation
reason
method
limit
offset
```

No browser-supplied filesystem path, SQL, free-form expression, principal identity, token, header, or request body is accepted.

## What is verified

Before returning any event, the lock-free snapshot reader verifies the entire configured JSONL chain:

1. source path does not traverse a symlink;
2. source bytes stay within the configured byte ceiling;
3. decoded content is strict UTF-8;
4. every line is a valid `SecurityAuditRecord`;
5. timestamps are timezone-aware;
6. event and operation values are within the canonical persisted vocabulary;
7. `previous_digest` links are continuous;
8. each record content digest matches its canonical payload;
9. record sequence is contiguous;
10. total records stay within the configured record ceiling.

The runtime store and read-only snapshot use the same chain parser so investigation semantics do not drift from runtime audit semantics.

## Privacy boundary

The persisted security event intentionally contains no request headers, request body, bearer token, credential, or principal object. The UI applies an additional privacy boundary:

- raw recorded paths are not returned;
- known protected routes are projected to route categories;
- a SHA-256 path digest supports bounded correlation without revealing the original path;
- known reason codes are shown as reason codes;
- arbitrary recorded reason text is replaced by `other-recorded-reason` and only its SHA-256 digest is retained;
- local journal filesystem paths are never sent to the browser.

The presence of a valid audit digest establishes integrity of the recorded entry, not semantic correctness of the host that emitted it.

## Runtime-containment configuration evidence

When `STATEWAKE_VERIFICATION_RUNTIME_SNAPSHOT` is configured, `statewake.server` atomically records the effective `VerificationServiceConfig` at application construction. The strict snapshot contains:

- request-body byte ceiling;
- read-only and HTTPS/insecure-HTTP flags;
- the number of configured artifact roots, but never the root paths;
- every `RuntimeContainmentLimits` value;
- a canonical SHA-256 digest over the snapshot payload.

The read API rejects unknown fields, symlink traversal, oversize data, malformed UTF-8/JSON, impossible scalar values, and configuration-digest mismatch. A configured snapshot is therefore evidence of the recorded effective service configuration at construction time. It is **not** proof that the process remains live.

The page also distinguishes actual service wiring from declared limits. Today the verification service directly enforces its request-body ceiling and uses `runtime_limits` for bounded JSON input bytes, depth, node count, and string/key bytes. Archive validation exists as a domain/operations control but custom service `runtime_limits` are not passed into that archive path. Graph-node, cooperative deadline, concurrency, and temporary-byte values likewise remain configured limits/primitives rather than active verification-service enforcement. The UI preserves these distinctions instead of promoting configuration into enforcement.

## Deployment boundary

`DeploymentSecurityConfig` remains an in-memory host-security configuration. StateWake still does not persist or verify a canonical snapshot of the live authentication provider, authorization provider, admission provider, TLS terminator, tenant-isolation configuration, KMS/HSM configuration, process/container policy, CPU/memory quotas, or network egress policy.

The investigation page therefore keeps four things separate:

```text
observed security-audit events
        !=
recorded verification-service containment configuration
        !=
repository deployment-security contract
        !=
verified live host configuration
```

The repository contract protects these operation categories when the deployment wrapper is used:

```text
verify:evidence
verify:proof
review:read
review:write
approval:read
approval:write
```

Authentication and authorization providers are host supplied. Request admission is host supplied and optional. The security event sink is host supplied and optional. HTTPS is required by the generic deployment boundary by default, while explicitly bounded local adapters may make different loopback-only choices.

## Interpretation rules

The UI must not translate recorded counts into a security score.

In particular:

```text
zero recorded failures
    != secure deployment

request_admitted
    != globally authorized business action

hash-linked audit continuity
    != complete event capture

recorded HTTPS rejection
    != proof that all traffic used correct TLS termination
```

A `request_admitted` record means that the configured `DeploymentSecurityConfig` wrapper reached its admitted branch for that request. It does not independently validate the correctness of the host authentication provider, authorization policy, admission provider, TLS termination, identity source, tenant isolation, or downstream application behavior.

## Failure states

The read API fails closed:

| Condition | HTTP result |
|---|---|
| no configured audit source | `404 SECURITY_AUDIT_SOURCE_NOT_CONFIGURED` |
| malformed/tampered/discontinuous source | `422 INVALID_SECURITY_AUDIT_SOURCE` |
| source exceeds byte/record ceiling | `413 SECURITY_AUDIT_SOURCE_TOO_LARGE` |
| runtime-containment snapshot is malformed/tampered/missing | `422 INVALID_RUNTIME_CONTAINMENT_SNAPSHOT` |
| runtime-containment snapshot exceeds its byte ceiling | `413 RUNTIME_CONTAINMENT_SNAPSHOT_TOO_LARGE` |
| invalid/duplicate/unsupported query | `400 INVALID_SECURITY_AUDIT_QUERY` |

A configured audit path that has not yet been created is represented as a missing journal with zero recorded events. That is not promoted into a healthy deployment result. A configured runtime-containment snapshot path that is absent, tampered, oversized, malformed, or redirected through a symlink fails closed instead of falling back to repository defaults.

## Non-goals

This capability does not:

- authenticate a caller;
- configure authorization policy;
- terminate TLS;
- implement tenant isolation;
- configure a KMS/HSM;
- harden the host OS/container;
- prove event-capture completeness;
- claim that configured graph/deadline/concurrency/temporary-byte values are actively enforced when the verification service does not wire them;
- prove current process liveness from a startup-time snapshot;
- perform penetration testing;
- authorize publication, deployment, release, or business action;
- replace the existing security assurance boundary verifiers.

It is a bounded operator reconstruction surface over existing StateWake deployment-security evidence.
