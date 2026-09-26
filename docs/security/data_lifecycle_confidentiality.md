# Tier 13 — Data Lifecycle & Confidentiality Protection

Tier 13 establishes an explicit lifecycle contract for sensitive StateWake information. It builds on existing sensitivity classification, privacy redaction, telemetry minimization, access controls, and retention semantics rather than creating a parallel data-governance system.

## Classification inheritance

Derived records inherit the highest sensitivity of their sources by default. A deliberate downgrade is an explicit decision and is rejected unless approval is provided at the boundary performing the transformation. Operational bundles enforce this rule across `derived_from` relationships.

## Lifecycle

Every governed data class should have a stated purpose, retention window, expiration condition, access boundary, and deletion behavior. Retention expiry is not itself permission to delete when a legal hold is active.

## Payload deletion and historical claim preservation

Deleting a payload is distinct from preserving the historical fact that the payload existed and participated in a reliability claim. `DeletionRecord` retains the object identity, digest, sensitivity, deletion time, policy, reason, and provenance references without retaining the deleted payload.

## Minimal disclosure

Telemetry and disclosure boundaries use sensitivity ceilings. Restricted material is not copied into lower-sensitivity telemetry. Portable proof consumers should request only the artifact set their audience is entitled to receive. The existing minimal-disclosure principle remains authoritative.

## Confidentiality boundaries

`DataLifecyclePolicy` exposes deployment requirements for encryption at rest and TLS without attempting to implement enterprise KMS, HSM, storage encryption, or transport termination inside StateWake. Encryption at rest and application authorization are distinct controls.

## Sensitive errors

HTTP validation errors remain generic and do not echo untrusted request payloads. Debugging output must not expose raw evidence, credentials, trust material, authorization headers, or internal filesystem details.

## Exit condition

Tier 13 is satisfied when StateWake-controlled data has explicit classification, purpose, minimization, access, retention, deletion/expiration, and disclosure semantics, with regression evidence for leakage and cross-boundary failures.

**Scope:** production-focused data lifecycle and confidentiality controls.


## Regression evidence

The Tier 13 regression suite covers classification inheritance, retention expiry and legal holds, payload deletion with historical tombstones, disclosure-ceiling export, telemetry leakage, generic HTTP errors, encryption/TLS policy declaration, operational-bundle classification enforcement, and cross-resource authorization isolation.

The content store performs deletion only through an explicit retention adapter and returns a payload-free `DeletionRecord`; the historical record can therefore preserve identity and digest without preserving deleted bytes.
