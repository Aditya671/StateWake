# Release Readiness Decision

**Current source version:** `v0.5.1`

**Current published public PyPI release:** `v0.4.1` — `Development Status :: 5 - Production/Stable`

**Historical GitHub release:** `v0.5.0` — immutable predecessor tag/release at an earlier source revision

This document records the published v0.4.1 PyPI baseline and the evidence required to qualify the approved v0.5.1 source candidate. The historical GitHub v0.5.0 record is retained as provenance and is not authority to reuse that version. A local version string or successful local verifier is not publication authorization; the exact tested candidate, external CI evidence, repository governance checks, protected-environment controls, and human publication approval remain separate controls.

## Current architecture

The active product is a framework-neutral reliability-evidence infrastructure layer. Its lifecycle is:

`execution → evidence → provenance → integrity → deterministic verification → reliability state → discrepancy/comparison → reconciliation/recovery → attestation/decision`

The current release line preserves the completed cybersecurity architecture through V3 Tier 15, the completed Persistence & Dataset Architecture through Tier 15, the v0.5.0 operational-trust/publication lifecycle, and the v0.5.1 reliability/production-hardening corrections.

## Required release evidence

- package metadata and `statewake.__version__` agree at `0.5.1`;
- `uv.lock` project identity agrees with package metadata;
- current API/reference documentation and current release notes identify v0.5.1;
- public API contract version remains `1`;
- source compilation and the active test suite pass;
- package/distribution boundary is verified in an environment with the declared dependencies;
- public Python and optional HTTP surfaces are exercised when claimed;
- source-tree and distribution checksums are recorded for the exact candidate;
- release documentation identifies the exact release boundary and known environment limitations;
- the four stable required CI contexts pass on the exact GitHub candidate revision;
- Release Verification builds and verifies the exact immutable distributions before publication.

## Publication boundary

The v0.4.1 package is already published as Production/Stable on PyPI, and v0.5.0 is a historical GitHub release/tag. For v0.5.1, a successful local candidate does not by itself authorize publication. The exact tested candidate, external CI evidence, repository governance checks, protected environment/Trusted Publisher configuration, and human publication approval remain separate controls.
