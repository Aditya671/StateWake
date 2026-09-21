# Release Information

## Current package baseline

**StateWake v0.4.0 — current release candidate/source baseline**

Distribution: `statewake-ai`

Import package: `statewake`

CLI: `statewake`

The public release sequence represented by this repository is:

- **v0.1.1** — Production/Stable packaging promotion of the v0.1.0 public package baseline. The supplied released source candidate is retained under `docs/releases/v0.1.1/`.
- **v0.2.0** — cybersecurity capability completion through V3 Tier 15.
- **v0.4.0** — Persistence & Dataset Architecture completion through Tier 15.

## Current scope

The v0.4.0 baseline combines the completed reliability lifecycle, cybersecurity architecture, and Persistence & Dataset Architecture. The workspace provides durable operational indexing, historical query/projection, tabular and portable exports, lifecycle/retention orchestration, integrity verification, analytical access, backend abstraction, and production workspace operations.

## Release boundary

Before external publication, verify:

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

The current sandbox intentionally did not install missing dependencies, so those dependency-backed gates remain explicit external work.

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

Release-specific records are organized under [`docs/releases/`](../releases/README.md). The executable local release-candidate coordinator remains `python scripts/release/verify_release_candidate.py` and does not authorize publication.
