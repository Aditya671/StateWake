# Changelog

## [v0.1.1] — Production/Stable packaging promotion

StateWake v0.1.1 promotes the verified v0.1.0 public package baseline to the `Development Status :: 5 - Production/Stable` classifier. This is a backward-compatible packaging and release-governance patch; no intentional public API or data-contract break is introduced.

### Release boundary

- Promoted package metadata from Beta to Production/Stable.
- Synchronized `pyproject.toml`, `statewake.__version__`, `uv.lock`, active release documentation, and executable release-version gates on `0.1.1`.
- Preserved the v0.1.0 public API contract version (`1`).
- Preserved v0.1.0 as the immutable preceding public release; no historical release artifact is overwritten.

All notable StateWake changes are recorded here. Historical implementation records remain in `repository history` and are not current release authority.

## [v0.1.0] — Strict quality and reliability hardening

### Time handling

- Replaced stale hard-coded timestamps in executable validation scripts and the golden runtime example with UTC runtime timestamps, while retaining deterministic historical timestamps in regression fixtures and historical scenarios.

### Static typing and lint correctness

- Fixed remaining Ruff and strict static-analysis diagnostics across validation scripts, package boundaries, domain models, services, and regression tests.
- Added missing public-module/function documentation and corrected invalid Ruff suppression directives.
- Corrected import ordering and intentional source-path bootstrap import handling.
- Removed unused validation variables and replaced unsafe blind assertions with explicit assertion errors.
- Preserved deterministic naive-datetime rejection tests without triggering timezone-construction lint diagnostics.

### Static typing and code quality

- Replaced generic dataclass metadata factories with explicitly typed string-to-string factories to prevent unknown-type propagation under strict Pylance/Pyright.
- Made file-ingestion keyword forwarding explicit so strict type analysis can prove the `ExternalEvidenceReceipt` return type.
- Generalized behavioral LCS matching to preserve the actual key element type and added explicit optional-index narrowing before sequence access.
- Added explicit `strict=` semantics to every `zip()` call.
- Migrated UTC handling to `datetime.UTC` and corrected property docstrings to noun/description form.
- Renamed public exception classes to `*Error` names while retaining non-exported compatibility aliases for the previous spellings.
- Removed targeted private helper usage from release/SDLC regression tests by using stable module-level helper names.
- Added typed validation-report contracts and runtime-validated API-manifest parsing to prevent unknown JSON values from reaching strict test assertions.

### Repository and engineering

- Reorganized documentation by responsibility: user guide, reference, architecture, specifications, development, testing, security, operations, governance, integrations, examples, ADRs, and historical archive.
- Reorganized project tooling into development, testing, integration, common, and release surfaces.
- Added an explicit StateWake SDLC, quality-gate matrix, and Definition of Done.
- Added repository structure and pull-request governance documentation.
- Added a deterministic SDLC verification coordinator for local and release workflows.
- Removed obsolete project-identity references from active and historical documentation and standardized the active identity on StateWake.

### Persistence and portability

- Corrected direct SQLite validation mutations to explicitly close database connections, eliminating the Windows file-handle retention defect behind `storage-corruption`.
- Added repository-local `data/` and disposable `data/validation/` storage boundaries.
- Added idempotent `SqliteReliabilityStateStore.initialize()` and a first-time local database initialization helper.
- Restored the verified `ZipInfo` behavior in the deep-chaos archive probe after historical implementation review.

### Verification

- Revalidated public documentation, executable examples, package identity, package boundaries, compatibility fixtures, script portability, property/state-machine validation, real-world scenarios, chaos validation, extreme validation, deep chaos, failure laboratory, and external integration fixtures.
- Native Ruff, Pyright/Pylance, and PyNaCl remain environment-dependent verification gates when unavailable in an isolated sandbox.

## [v0.1.0] — Packaging and documentation correction

StateWake v0.1.0 is a backward-compatible patch release following the initial TestPyPI publication.

### Packaging and documentation

- Corrected the package README for PyPI/TestPyPI rendering and consumer onboarding.
- Replaced repository-relative README documentation links with canonical GitHub links so documentation remains reachable from the package index.
- Removed repository-only development instructions from the package landing page.
- Added canonical GitHub project, repository, issue, documentation, changelog, and security metadata to package configuration.
- Preserved the StateWake v0.1.0 runtime/API baseline; this patch changes packaging and documentation presentation only.

## [v0.1.0] — StateWake initial public package baseline

StateWake v0.1.0 is the current package baseline. The release candidate process requires deterministic automated verification followed by explicit human release approval.

### Product

- Evidence-backed reliability infrastructure for AI systems.
- Canonical evidence admission, provenance, integrity, reliability state, reconciliation/recovery, attestation, and proof lifecycle.
- Framework-neutral integration SDK and first-party evidence adapters.
- Public Python API, CLI, and WSGI HTTP verification adapter.
- Three synthetic golden reference applications and credential-free cross-domain scenarios.

### Reliability and security

- Deterministic failure-laboratory, property/state-machine, chaos, deep-chaos, and extreme validation campaigns.
- Persistent trust checkpoints and explicit integrity, replay, identity, provenance, recovery, privacy, and archive-security controls.
- Package-boundary and compatibility-fixture verification.

### Historical provenance

Earlier implementation records are preserved under `repository historyhistorical-evaluations/` for engineering archaeology only. They do not define the current StateWake architecture, API, roadmap, or release identity.
