# Tier 5 — Continuous Security Assurance

## Status

This document defines the StateWake Tier 5 **development assurance** mechanism. It is not a release approval, certification, vulnerability-scanning program, or deployment-security substitute.

## Purpose

Tier 5 makes the Tier 4 security invariants change-aware. A previously verified result is not silently reused after relevant implementation, configuration, dependency, security-evidence, or test changes.

## Assurance states

```text
VERIFIED → STALE → REVERIFYING → VERIFIED
                 ↘
                  ASSURANCE_BROKEN → QUARANTINED / DEGRADED
```

The executable mechanism records these states and never converts an unknown, missing, or failed verification into `VERIFIED`.

## Change-impact model

The verifier compares a SHA-256 snapshot of the current repository with the last promoted Tier 5 baseline. Its `snapshot_fingerprint` is an **assurance-snapshot identity** derived from the path/digest manifest. It is intentionally distinct from the Tier 8 `source_tree_sha256`, which is a content-bound source-tree digest used for source-to-artifact provenance. These identifiers are not interchangeable and must not be substituted for one another in evidence records. Impact is classified from repository paths into security-invariant families:

| Change family | Reverification scope |
|---|---|
| Evidence/provenance/reliability/state | Evidence integrity, provenance integrity, reliability-state integrity, attestation integrity |
| Trust-anchor/signing/key management | Cryptographic and trust-anchor controls |
| Deployment/auth/security-audit | Authorization, boundary, audit, transport assumptions |
| Archive/proof verification | Portable-proof integrity |
| Persistence/recovery/storage | Persistence and recovery security assumptions |
| Dependency/configuration | Potentially all security invariants |
| Security model/control/ADR/recovery evidence | Security-assurance evidence consistency |
| Other `src/` changes | Conservative security re-assurance |
| Documentation/tests only | No product-control invalidation unless security evidence/tests are affected |

The model is deliberately conservative where the existing architecture does not expose finer-grained dependency metadata.

## Re-verification mechanism

`scripts/security/verify_continuous_security_assurance.py` provides a read-only assurance calculation by default and can run the existing Tier 4 verifier when relevant changes are detected. It emits a machine-readable result containing:

- candidate fingerprint;
- baseline fingerprint;
- changed files;
- impact classifications;
- invariants requiring re-verification;
- executed re-verification result;
- final assurance state;
- residual-risk and limitation context.

A successful result can then be promoted by replacing the Tier 5 baseline snapshot with the verified candidate snapshot. Promotion is a development-baseline operation and does not change the package version or publish a release.

## Stale-result handling

A result is `STALE` when the current candidate fingerprint differs from the fingerprint recorded by the last assurance result and no successful re-verification has established the new candidate. A failed re-verification is `ASSURANCE_BROKEN`. A relevant change that has not yet been reverified must never be represented as current verification.

## Evidence boundaries

Tier 5 does not establish host-OS security, runtime hardening, TLS termination, authentication infrastructure, KMS/HSM controls, rate limiting, repository governance, or external producer security. Those remain deployment or external-system responsibilities already documented by the Tier 4 security model.

## Exit condition

Tier 5 evidence is sufficient when StateWake can determine, from executable evidence, whether an assurance result is current, what changed since the promoted baseline, which invariants require re-verification, whether re-verification passed or failed, which assurance state applies, and which residual risks remain.

## Development-only boundary

The current package identity is `v0.4.0`. This tier is a promoted development assurance baseline only. No release tag, publication, or release artifact is authorized by this document.
