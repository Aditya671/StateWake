# Tier 12 — Runtime & Hostile-Input Containment

Status: promoted development-assurance baseline; not a release.

## Objective

Tier 12 establishes explicit containment boundaries around untrusted evidence, portable proof packages, structured JSON, archive members, external references, and verification work. It composes the existing admission, archive-hardening, read-only verification, and deployment-security controls rather than creating a parallel verifier.

The invariant is:

> Untrusted input may influence verification results, but it must not acquire unintended execution authority or unlimited computational authority.

## Existing capability reused

The repository already had the following controls before Tier 12:

- request-size enforcement in `src/statewake/server.py`;
- artifact-root containment and read-only verification;
- deterministic ZIP creation and duplicate-member/path checks;
- manifest/member-size checks;
- failure/chaos/extreme validation;
- provider-owned authentication, authorization, request admission, and TLS boundary;
- temporary-directory use for proof materialization;
- no private signing-key ownership in StateWake;
- portable verification that does not execute archive content.

Tier 12 therefore adds only the missing reusable containment contract and applies it at the risky parsing/archive boundaries.

## Runtime containment contract

`src/statewake/domain/runtime_containment.py` provides typed, deterministic checks for:

- maximum input bytes;
- maximum archive members;
- maximum aggregate and per-member uncompressed archive bytes;
- maximum compression ratio;
- maximum JSON nesting depth;
- maximum JSON node count;
- maximum UTF-8 string/key size;
- maximum cooperative verification time via a monotonic deadline;
- maximum concurrency and temporary-byte budget as deployment policy parameters;
- external-reference scheme validation.

Defaults are deliberately bounded development-safe envelopes. Deployment owners may override the values for their workload; enterprise-specific values are not embedded in pure business semantics.

## Archive safety

Archive verification performs metadata preflight before reading member bodies. Unsafe paths, symlinks, excessive member counts, excessive aggregate expansion, oversized members, and extreme compression ratios are rejected. Archive contents are data only and are never executed as scripts, binaries, macros, plugins, or configuration.

## JSON safety

The HTTP adapter and portable verifier enforce a byte-size envelope before JSON decoding and then walk the decoded structure for nesting, node-count, and string-size limits. A hostile object is rejected deterministically instead of being allowed to grow without a contract.

## Network egress

Evidence references are data. The portable verifier does not fetch them. URI-bearing references must use an explicitly approved scheme; by default no external scheme is approved. Resolution, when required by a deployment, belongs behind an approved host/provider boundary.

## Isolation requirements

High-risk verification should be deployed in a least-privilege worker/process/container where the workload warrants it. The worker should have read-only evidence access, no signing keys, no unnecessary network egress, bounded CPU/memory/concurrency, and a dedicated temporary root with controlled permissions and cleanup. These properties are deployment requirements and are not falsely claimed as enforceable by the pure domain layer.

## Verification behavior

Containment failures are deterministic failures, not successful verification results. The evidence verifier must preserve its existing trust/verification outcomes and must not convert a resource-limit rejection into a verified state.

## Tier 12 regression coverage

The dedicated suite covers archive bombs, compression ratio, deep JSON, object counts, oversized strings, malformed packages, traversal and symlinks, external-reference rejection, verification deadlines, server request-size handling, archive non-execution, and bounded archive expansion.

The inherited end-to-end suite remains mandatory; Tier 12 is not promoted by focused tests alone.

## Exit condition

Tier 12 is satisfied for the development baseline when untrusted-input boundaries have explicit validation, resource envelopes, containment/isolation requirements, safe archive processing, no implicit execution, no arbitrary external network dependency, and executable tests demonstrating bounded failure behavior.
