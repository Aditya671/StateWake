# Versioning Policy

## Current package version

**StateWake: `v0.1.1`**

`v0.1.1` is the current canonical production/stable package baseline. `v0.1.0` remains the preceding public package baseline and is not modified. Historical `0.0.x`–`0.6.x` identifiers are implementation provenance and do not define the current public version.

## Version sources of truth

The package version is defined in `pyproject.toml` and exposed as `statewake.__version__`. Release automation and tests must verify these values agree with each other.

`uv.lock` must resolve the same project version. Documentation must refer to the current version as `v0.1.1` unless explicitly describing historical implementation evidence.

## Semantic versioning policy

- **MAJOR**: incompatible public Python API, data-contract, or HTTP API changes.
- **MINOR**: backward-compatible public capabilities or new integration surfaces.
- **PATCH**: backward-compatible fixes, verification hardening, documentation corrections, and packaging fixes.
- Historical phase numbers are not versioning authority.

## Historical numbers

The repository accumulated a long implementation sequence from `0.0.0` through `0.5.58`. Those numbers remain in historical documentation where they explain how an implementation was produced, but they are not independent public compatibility guarantees.

The current StateWake product line remains compatible with the `v0.1.0` public baseline; `v0.1.1` promotes that baseline to Production/Stable through a backward-compatible packaging/governance patch.

## Release gates

A public release requires all of the following:

1. package metadata and `__version__` agree;
2. changelog and active documentation agree;
3. source and tests are AST-clean and compile cleanly;
4. full active test suite passes;
5. wheel/sdist build succeeds and a fresh installation imports successfully;
6. public Python API is independently exercised from a clean consumer project;
7. optional HTTP API is independently exercised when claimed as a release surface;
8. no active import depends on the repository history archive;
9. architecture decision explicitly confirms the release boundary against `StateWake-ai.pdf`;
10. release artifact is checksum-locked.

A public developer release may use the standard-library WSGI adapter as a local/internal edge; an internet-facing hosted service requires separate security architecture and is not implied by package release.
