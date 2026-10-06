# Release Readiness Decision

**Current source version:** `v0.5.0`

**Current published public release:** `v0.4.1` — `Development Status :: 5 - Production/Stable`

This document records the published v0.4.1 baseline and the evidence required to qualify the current v0.5.0 source candidate. Publication of v0.4.1 is an established package-release state; v0.5.0 is not treated as published or release-ready by a version change alone. Individual source/security verifiers remain bounded evidence checks and are not themselves publication authorities.

## Current architecture

The active product is a framework-neutral reliability-evidence infrastructure layer. Its lifecycle is:

`execution → evidence → provenance → integrity → deterministic verification → reliability state → discrepancy/comparison → reconciliation/recovery → attestation/decision`

The current release line preserves the completed cybersecurity architecture through V3 Tier 15 and the completed Persistence & Dataset Architecture through Tier 15.

## Required release evidence for subsequent releases

- package metadata and `statewake.__version__` agree;
- `uv.lock` project identity agrees with package metadata;
- public API contract version remains `1` unless a breaking contract change is intentionally introduced;
- source compilation and the active test suite pass;
- package/distribution boundary is verified in an environment with the declared dependencies;
- public Python and optional HTTP surfaces are exercised when claimed;
- source-tree and distribution checksums are recorded for the exact candidate;
- release documentation identifies the exact release boundary and known environment limitations.

## Publication boundary

The v0.4.1 package is already published as Production/Stable. For v0.5.0 and later releases, a successful local candidate does not by itself authorize publication. The exact tested candidate, external CI evidence, repository governance checks, and human publication approval remain separate controls.
