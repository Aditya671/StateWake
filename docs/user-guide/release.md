# Release Information

## Current development baseline

**StateWake v0.1.1 — Production/Stable baseline**

Distribution: `statewake-ai`

Import package: `statewake`

CLI: `statewake`

This artifact is a pre-1.0 development baseline. It is not, by itself, an approval to publish a new package release.

## Current scope

The canonical baseline contains the verified StateWake reliability-evidence lifecycle through the external-integration validation boundary, including the integration SDK, synthetic golden applications, failure laboratory, property/state-machine verification, persistent trust anchors, public API contract, and external evidence capture.

## Release boundary

Before publication, verify:

1. package and import versions agree;
2. changelog and active documentation agree;
3. source and compilation checks pass;
4. all active tests pass;
5. wheel and source distributions build;
6. a fresh environment can install and import the wheel;
7. the public Python integration is exercised independently;
8. HTTP integration is exercised when included in the release claim;
9. active code has no dependency on the historical archive;
10. repository-level and platform-specific release gates are externally verified;
11. the final artifact is checksum locked.

The current isolated sandbox cannot assert GitHub server-side governance or native availability of every optional development tool. Those remain explicit external gates rather than hidden assumptions.

See [Limitations](limitations.md) and the [Release Evidence Index](release-evidence-index.md) for the supported product claims and their evidence boundaries.

## Reliability evidence to proof flow

```text
producer artifact
  → first-party adapter / external receipt
  → canonical admission
  → evidence chain
  → claim-profile evaluation
  → decision-basis preparation and chain binding
  → reliability-state transition
  → outcome attestation
  → release-proof verification and portable proof bundle
```

## release-candidate process

The repository now includes an executable local release-candidate coordinator: `python scripts/release/verify_release_candidate.py`. It records release identity, compatibility, product-experience, compilation, build, package-boundary, and deterministic provenance evidence. It intentionally does not authorize publication. See [`../governance/RELEASE_CANDIDATE_PROTOCOL.md`](../governance/RELEASE_CANDIDATE_PROTOCOL.md).
