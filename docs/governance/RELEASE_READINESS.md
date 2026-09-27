# Release Readiness Decision

**Current source candidate:** `v0.4.1`

**Last recorded public release:** `v0.4.0`

This document records the v0.4.1 source candidate and the evidence required before its publication. Each future publication remains a separate human authorization and platform gate.

## Current architecture

The active product is a framework-neutral reliability-evidence infrastructure layer. Its lifecycle is:

`execution → evidence → provenance → integrity → deterministic verification → reliability state → discrepancy/comparison → reconciliation/recovery → attestation/decision`

The current release line preserves the completed cybersecurity architecture through V3 Tier 15 and the completed Persistence & Dataset Architecture through Tier 15.

## Required release evidence

- package metadata and `statewake.__version__` agree;
- `uv.lock` project identity agrees with package metadata;
- public API contract version remains `1` unless a breaking contract change is intentionally introduced;
- source compilation and the active test suite pass;
- package/distribution boundary is verified in an environment with the declared dependencies;
- public Python and optional HTTP surfaces are exercised when claimed;
- source-tree and distribution checksums are recorded for the exact candidate;
- release documentation identifies the exact release boundary and known environment limitations.

## Publication boundary

For future releases, a successful local candidate does not by itself authorize publication. The exact tested candidate, external CI evidence, repository governance checks, and human publication approval remain separate controls.
