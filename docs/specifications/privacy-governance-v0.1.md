> **Specification classification:** Supporting-producer compatibility specification.
>

# Privacy, Redaction + Evidence Governance v0.1

## Purpose

Keep sensitive values out of canonical metadata and telemetry where explicit policy can establish the result. The implementation is deterministic and local-first; it does not inspect opaque evidence content.

## Redaction

`PrivacyPolicy` defines explicit metadata keys and regular-expression rules. `Redactor` applies them recursively to JSON-like mappings and event metadata. Redaction preserves event identity, sequence, timestamps and payload references.

The default key set covers common secret-bearing metadata names such as `authorization`, `api_key`, `password`, `token`, `email`, `phone`, `ssn`, and `secret`. Applications can replace the key set explicitly and add deterministic regex rules.

## Evidence classification

`EvidenceItem.sensitivity` is one of `public`, `internal`, `confidential`, or `restricted`.

`EvidenceGovernancePolicy` separately defines:

- the maximum sensitivity permitted in local content storage;
- the maximum sensitivity represented in telemetry;
- sensitivities that must carry a content digest.

Telemetry is metadata-only: evidence above the telemetry ceiling is omitted from a telemetry projection rather than copied with redaction.

## Content handling boundary

The engine does not attempt to scan arbitrary binary or document contents for secrets. Sensitive content should be referenced by `content_ref` or represented by a digest, and storage must pass the explicit governance policy before bytes are written.

## Runtime integration

The production ingestion boundary accepts an explicit `PrivacyGovernanceRuntimeConfig` that combines the existing privacy and evidence-governance policies. When configured, the canonical order is:

```text
metadata redaction
    -> receipt identity construction
    -> evidence sensitivity classification
    -> storage-governance evaluation
    -> content-addressed artifact write
    -> durable receipt write
    -> workspace sensitivity/policy indexing
```

A storage rejection occurs before either artifact bytes or the receipt are written. The caller must supply the explicit evidence sensitivity; unsupported sensitivity values are rejected before persistence. Existing AI-contract capture propagates the contract's sensitivity into this boundary.

The OpenTelemetry bridge can consume the same runtime configuration plus an `EvidenceManifest`. It projects only evidence IDs at or below `telemetry_max_sensitivity`; excluded IDs are omitted, not replaced with redaction markers. Event metadata still passes through the configured `Redactor`.

Opaque artifact content is not secret-scanned. Telemetry visibility is not evidence of disclosure authorization, producer authenticity, factual correctness, or a live exporter binding.

## Runtime policy evidence

A configured workspace may emit a bounded `privacy-governance-runtime.v1` snapshot. The snapshot records the effective policy configuration and enforcement contract, carries a deterministic SHA-256 digest, is written atomically with restrictive permissions, and is loaded with symlink rejection plus a configured byte ceiling. The snapshot contains policy rules because it is a local runtime evidence artifact; browser projections expose only policy identity/counts and governance ceilings, not regex patterns or replacement values.

## Definition of done

A deployment/runtime integration can redact sensitive event metadata before receipt persistence or telemetry, classify evidence by sensitivity, reject disallowed evidence storage before artifact writes, durably retain the applied policy/sensitivity in the workspace index, and deterministically project only permitted evidence references into telemetry without changing the reliability domain model.
