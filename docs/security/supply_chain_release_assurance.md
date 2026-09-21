# Tier 8 — Supply-Chain & Release Assurance

## Status

This document defines the StateWake Tier 8 **development assurance** mechanism. It is not a release approval, certification, production-readiness approval, or publication authorization.

## Objective

Tier 8 binds the existing StateWake release-verification plumbing into one inspectable provenance contract:

```text
source tree
  ↓
locked dependency state
  ↓
build context + build steps
  ↓
security-test evidence
  ↓
exact artifact digest
  ↓
verification result
  ↓
release/publication boundary
```

The intent is not to create a generic DevSecOps platform. It is to make the provenance of a StateWake artifact explicit and mechanically checkable.

## Existing capabilities reused

Tier 8 does not duplicate the existing release system. It reuses:

- `pyproject.toml` for distribution identity, version, dependency declarations, and build backend;
- `uv.lock` for locked dependency identity and artifact hashes;
- `.github/workflows/release-verification.yml` for lock validation, build, checksums, clean-consumer validation, dependency audit, SBOM generation, and build-provenance attestation;
- `scripts/release/verify_release_candidate.py` for existing release-candidate gates and deterministic tree evidence;
- the existing release-governance documents for the human approval and publication boundary.

The missing capability was the binding record that joins those facts to the **exact artifact** and to the source/dependency state against which security evidence was produced.

## Provenance contract

Tier 8 also validates the repository `verification_manifest.txt` against the exact immutable source-tree file set. The manifest excludes only the self-referential candidate identity files (`verification_manifest.txt` and `candidate-fingerprint.txt`), and every remaining path must be present exactly once with its current SHA-256 digest. This prevents release evidence from silently describing an older or partial candidate.

`candidate-fingerprint.txt` records the Tier 8 `source_tree_sha256`. It is intentionally distinct from the Tier 5 assurance snapshot fingerprint; the two identifiers have different canonicalization and evidence semantics and are not interchangeable.

A Tier 8 provenance record contains at minimum:

- schema version;
- development/release status;
- distribution and version identity;
- explicit source revision/fingerprint;
- source-tree SHA-256 digest;
- dependency-lock SHA-256 digest;
- build context;
- build steps;
- security-test results bound to the same source and dependency digests;
- exact artifact name, size, and SHA-256 digest;
- verification status bound to the exact artifact;
- explicit publication authorization state.

`scripts/release/verify_supply_chain_provenance.py` validates this record and, when an artifact path is supplied, recomputes the artifact digest rather than trusting the recorded value.

## Dependency integrity boundary

`uv.lock` is treated as the authoritative locked dependency state for this repository. Tier 8 verifies that declared runtime dependencies **and every declared optional-extra dependency** are represented in the lock and that the lock itself is digest-bound in the provenance record. This prevents implemented optional adapter packages from silently existing only in source code or documentation.

A package name and version are not treated as sufficient proof of artifact identity. The existing lockfile and CI workflow provide the stronger package/artifact hash and external repository controls; Tier 8 records the lock identity used by the candidate.

## Build provenance boundary

A build record must answer:

1. What source state was used?
2. What dependency-lock state was used?
3. What build environment was used?
4. What build steps ran?
5. What security tests ran against that state?
6. What exact artifact resulted?
7. What verification result was bound to that artifact?

The repository cannot independently prove the security of the CI runner, GitHub account, package index, external artifact storage, or administrative controls. Those remain deployment/CI-provider responsibilities and are explicitly residual risk.

## Artifact substitution

The primary Tier 8 local invariant is:

```text
verified source + dependencies + tests
        ↓
artifact SHA-256
        ↓
verification record
```

A substituted artifact must therefore produce a digest mismatch and fail verification.

## Security-test provenance

A security result is only reusable for this assurance contract when it is bound to both:

```text
source-tree digest
+
dependency-lock digest
+
passed result
```

This prevents a green result from one source/dependency state from being silently presented as evidence for another state.

## Development-only boundary

This tier is intentionally usable for development baselines without authorizing publication. The current package identity is `v0.3.0`. The workspace extra is the explicit dependency surface for the v0.3.0 dataset/export/analytical adapters. A provenance record must explicitly carry `release_status = development-only` and `publication_authorized = false` for this workflow.

A successful Tier 8 verification therefore means **the described development artifact is internally attributable and integrity-bound**. It does not mean that a public release is approved or that external CI/repository controls have been independently audited.

## Exit condition

Tier 8 is complete for this development baseline when a relying party can establish:

- what source produced the artifact;
- what locked dependencies were used;
- what build context and steps were declared;
- what security evidence was produced against that exact source/dependency state;
- what exact artifact digest was verified;
- that the verification record is bound to that artifact;
- that the evidence does not itself authorize publication.

## Residual risk

The repository-side verifier cannot prove:

- Git hosting administrator integrity;
- CI runner integrity;
- package-index compromise resistance beyond locked hashes and external controls;
- external SBOM/attestation service correctness;
- administrative separation of release authorities;
- operational publication controls.

Those boundaries are documented rather than silently converted into repository-level passes.
