# Release Information

## Source and public release versions

**Current source version: StateWake v0.5.1**

**Current published public release: StateWake v0.4.1**

PyPI maturity classifier: `Development Status :: 5 - Production/Stable`.

Distribution: [`statewake-ai`](https://pypi.org/project/statewake-ai/)

Import package: `statewake`

CLI: `statewake`

The public release sequence represented by this repository includes:

- **v0.1.1** — Production/Stable packaging promotion of the v0.1.0 public package baseline. The supplied released source record is retained under `docs/releases/v0.1.1/`.
- **v0.2.0** — cybersecurity capability completion through V3 Tier 15.
- **v0.4.0** — Persistence & Dataset Architecture completion through Tier 15.
- **v0.4.1** — current published Production/Stable reliability and integration update.
- **v0.5.0** — historical GitHub operational-trust tag/release at its original source revision; it is not reused.
- **v0.5.1** — approved current patch candidate for cumulative operational-trust capability plus post-tag reliability, CI/release orchestration, and production-readiness hardening; not yet published to PyPI.

## Current scope

The published v0.4.1 release preserves the v0.4.0 baseline and incorporates the v0.4.1 reliability, native integration, security-assurance, workspace, and release-evidence updates recorded in the changelog. The workspace provides durable operational indexing, historical query/projection, tabular and portable exports, lifecycle/retention orchestration, integrity verification, analytical access, backend abstraction, and production workspace operations.

## Release boundary for future versions

For a future package publication, verify:

1. package and import versions agree;
2. changelog and active documentation agree;
3. source and compilation checks pass;
4. all dependency-backed active tests pass;
5. wheel and source distributions build;
6. a fresh environment installs and imports the exact candidate;
7. the public Python integration is exercised independently;
8. HTTP integration is exercised when included in the release claim;
9. active code has no dependency on historical engineering archives;
10. repository-level and platform-specific release gates are externally verified;
11. the exact source/distribution artifacts are checksum locked.

Historical v0.4.0 local-gate results remain historical evidence and must not be substituted for the v0.4.1 release record. Likewise, a local verifier run against v0.4.1 proves only the boundary it actually checks; it does not retroactively establish PyPI provenance or independently authorize a later publication.

For v0.5.1 and later, the redesigned GitHub Release Verification workflow is the distribution-build authority. It retains the exact distributions, SHA-256 checksums, source revision, and release-candidate/SDLC evidence. Manual TestPyPI publication requires an explicit successful verification run ID. A production GitHub Release resolves the exact release commit and waits, within a bounded timeout, for the matching Release Verification run instead of assuming verification has already finished. Publication preparation then revalidates those immutable artifacts, records target-specific authorization, and issues a fresh permit without OIDC permission. The protected registry job receives only the prepared distributions and performs the Trusted Publishing upload; it does not build, test, or authorize source.

## Evidence flow

```text
producer artifact
  → first-party adapter / external receipt
  → canonical admission
  → evidence chain
  → verification / reliability state
  → reconciliation / recovery
  → attestation / decision
  → durable workspace
  → query / projection / export / analysis
```

## Release evidence

Release-specific records are organized under [`docs/releases/`](../releases/README.md). The executable release-candidate coordinator remains `python scripts/release/verify_release_candidate.py`; it validates a candidate but does not independently authorize a future publication.
