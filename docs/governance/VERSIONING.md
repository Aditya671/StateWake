# Versioning Policy

## Current package version

**StateWake source: `v0.5.1`**

The exact `v0.5.1` version is approved for the current candidate. The current published Production/Stable PyPI baseline remains `v0.4.1`. GitHub already contains an immutable historical `v0.5.0` tag/release at an earlier source revision; that tag is retained as history and must not be moved, deleted, or reused.

The public release sequence is:

- `v0.1.1` — Production/Stable packaging promotion of the v0.1.0 public package baseline.
- `v0.2.0` — cybersecurity capability release completing the V1/V2/V3 security progression through V3 Tier 15.
- `v0.4.0` — AI Systems Seven-Phase Roadmap release completing AI evidence contracts, claim profiles, reports, workspace guarantees, integrations, release trust, and comparative validation.
- `v0.4.1` — current published Production/Stable PyPI reliability, native-integration, and assurance-consistency update.
- `v0.5.0` — historical GitHub release/tag for the operational-trust and publication-lifecycle capability line.
- `v0.5.1` — approved current patch candidate carrying the cumulative v0.5.0 capability line plus post-tag reliability, CI, release-orchestration, production-readiness, and version-identity hardening.

Historical implementation identifiers remain provenance and do not override these public package versions. The published v0.4.1 package remains the public PyPI baseline until v0.5.1 completes external CI, release verification, protected-environment authorization, and registry publication.

## Version sources of truth

The package version is defined in `pyproject.toml` and exposed as `statewake.__version__`. `uv.lock` must resolve the same project version. Active API/reference documentation, current release notes, UI source-line labels, and release guidance must identify the same current version.

The public API contract version remains `1` because v0.5.1 is a backward-compatible patch release and does not introduce an incompatible Python API, data-contract, HTTP API, or serialization break.

## Semantic versioning policy

- **MAJOR**: incompatible public Python API, data-contract, or HTTP API changes.
- **MINOR**: backward-compatible public capabilities or new integration surfaces.
- **PATCH**: backward-compatible fixes, verification hardening, documentation corrections, packaging fixes, CI/release orchestration hardening, and production-readiness corrections.
- Historical phase numbers are implementation provenance, not versioning authority.

## Release sequence rationale

`v0.1.1` is a patch because the supplied release candidate documents a packaging/governance promotion without an intentional public API or data-contract break.

`v0.2.0` is a minor release because it introduces the completed cybersecurity capability set and additional security-facing public surfaces without changing the public contract version.

`v0.4.0` is a minor release because it introduces the completed StateWake AI Systems Seven-Phase Roadmap while preserving existing public contracts.

`v0.4.1` is the published patch release for cumulative compatible changes after v0.4.0. Its changelog includes native SDK integration surfaces, an explicit pre-1.0 versioning exception retained for the published release.

`v0.5.0` records the historical GitHub operational-trust release boundary. The current source advanced beyond that immutable tag before production PyPI publication.

`v0.5.1` is a patch because the post-tag changes are backward-compatible reliability fixes and release/CI hardening: deterministic test cleanup, read-only SDLC verification, platform corrections, immutable-artifact publication orchestration, production-activation controls, and version-accurate registry transport identity. No public API contract bump is required.

## Release discipline

Each release must be assessed against the exact candidate identity, synchronized version sources, compatibility evidence, security evidence, package boundary, documentation, and external publication gates. Version changes do not authorize publication by themselves. Commit, tag, GitHub Release, TestPyPI/PyPI publication, and registry reconciliation remain separate actions.
