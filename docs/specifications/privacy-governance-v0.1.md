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

## Definition of done

A deployment/runtime integration can redact sensitive event metadata before persistence or telemetry, classify evidence by sensitivity, reject disallowed evidence storage, and deterministically project only permitted evidence references into telemetry without changing the reliability domain model.
