# Versioning Policy

## Current package version

**StateWake: `v0.4.0`**

The public release sequence is:

- `v0.1.1` — Production/Stable packaging promotion of the v0.1.0 public package baseline.
- `v0.2.0` — cybersecurity capability release completing the V1/V2/V3 security progression through V3 Tier 15.
- `v0.4.0` — AI Systems Seven-Phase Roadmap release completing AI evidence contracts, claim profiles, reports, workspace guarantees, integrations, release trust, and comparative validation.

Historical implementation identifiers remain provenance and do not override these public package versions.

## Version sources of truth

The package version is defined in `pyproject.toml` and exposed as `statewake.__version__`. `uv.lock` must resolve the same project version. Active release documentation must identify the same current version.

The public API contract version remains `1` across this release sequence because the requested releases are treated as backward-compatible additions/promotions rather than incompatible contract changes.

## Semantic versioning policy

- **MAJOR**: incompatible public Python API, data-contract, or HTTP API changes.
- **MINOR**: backward-compatible public capabilities or new integration surfaces.
- **PATCH**: backward-compatible fixes, verification hardening, documentation corrections, and packaging fixes.
- Historical phase numbers are implementation provenance, not versioning authority.

## Release sequence rationale

`v0.1.1` is a patch because the supplied release candidate documents a packaging/governance promotion without an intentional public API or data-contract break.

`v0.2.0` is a minor release because it introduces the completed cybersecurity capability set and additional security-facing public surfaces without changing the public contract version.

`v0.4.0` is a minor release because it introduces the completed StateWake AI Systems Seven-Phase Roadmap while preserving existing public contracts.

## Release discipline

Each release must be assessed against the exact candidate identity, synchronized version sources, compatibility evidence, security evidence, package boundary, documentation, and external publication gates. Version changes do not authorize publication by themselves.
