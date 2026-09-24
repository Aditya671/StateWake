# Changelog

## Unreleased — Native SDK integration development copy
- Improved Phase 7 negative-trial findings: `broken_provenance_edge` and `invalid_reliability_transition` now exercise their distinct existing domain validators instead of inheriting detection from a generic failed-profile fixture. Preserved structural profile and underlying evidence verification as separate results; added positive/negative control regressions.
- Corrected prior release-boundary overreach: centralized current-project file selection for provenance, release-candidate fingerprint, Tier 5 security snapshots, and current-identity scans; excluded historical audit copies, prior release notes, generated reports, and scratch files without excluding live source, verification scripts, tests, build inputs, or shipped wheel contents.
- Removed only the duplicated historical audit report/catalog copies from the clean runnable candidate; earlier release records and active scripts remain intact.
- Historical: an earlier pass included all `docs/verification/` in the fingerprint; superseded by the current explicit release-input boundary.
- Improved prior-release design findings through opt-in independently pinned Ed25519 producer-receipt and release-signature verification; kept structural claims, observed content, signer authentication and human publication approval separate.
- Bounded native failure-journal disk use, rejected symlinked journal paths and malformed records, and restricted native metadata to printable bounded scalars without arbitrary SDK stringification.
- Restored the missing design-gap implementation record; explicitly documented machine-dependent gates and noncooperative-writer/privacy/producer-honesty limits.
- Improved prior-release design gaps D11/D12/D14/D16: fail-closed missing mapping observations, bounded native capture with optional durable failures and workspace persistence, distinct point-in-time checkpoint/event contracts, and candidate-only maturity labeling. D07 and external trust boundaries remain open.


- Improved prior-release design-gap findings D11, D13 and D15: fail-closed persisted capture timestamps and payload digest binding, GenAI-only native span admission, and Markdown-safe human-report field rendering; added reproducible negative tests and recorded remaining audit findings in `docs/verification/design-audit-pending-defects-followup.md`.

- Improved prior-release trust boundaries: restricted integration metadata to explicit flat identity/status fields; unknown payload aliases and nested secrets no longer pass into evidence metadata.
- Improved workspace backups using SQLite online snapshots for committed WAL changes, single-read member digest binding and exclusion of transient database sidecars.
- Added opt-in workspace-backed AI-contract profile evaluation, preserving the original structural profile API while requiring persisted receipt/payload verification for content-backed claims.
- Added release-trust local file verification for artifact/SBOM/scan/test/provenance digests, distinctly limited from cryptographic signature and producer trust verification.
- Recorded the remaining SDK, lockfile and external-writer boundaries in `docs/verification/trust-boundary-followup.md`.

- Improved prior-release trust boundaries: rejected source-text AI-contract spoofing, made benchmark detection evidence-based rather than table-declared, redacted nested report fields, and made backup restoration staged and exact rather than an overlay.
- Added negative regressions and regenerated Phase 7 reports/metrics; documented unresolved content resolution, privacy, WAL snapshot, release-trust and dependency-lock gates in `docs/verification/whole-artifact-trust-boundary-remediation.md`.

- Improved prior-release architecture in the current code: removed five verified-unused private helpers from provenance, JSON export, reconciliation binding, lineage, and proof-bundle services without changing their public interfaces or historical release records.
- Preserved actively used private helpers and white-box tests; documented the focused audit, regression results, and outstanding SDK/lockfile gates in `docs/verification/native-integration-release-and-private-boundary-audit.md`.
- Added native OpenAI Agents, LangChain, LangGraph, LlamaIndex and OpenTelemetry observation hooks without replacing the existing Phase 5 adapters.
- Added framework-specific optional dependencies and an all-framework integrations extra; lockfile refresh requires online resolution and full SDK compatibility validation.
- Added native callback/checkpoint tests, visible capture failures, and safe metadata selection.
- Documented limitations and install procedures in `docs/integrations/native-framework-capabilities.md`.
- Tightened native capture to reject missing completion timestamps and hash observed structured SDK content canonically rather than via Python object representations.
- Added explicit regression tests for timestamp completeness, deterministic structured digests, and absence of raw observed content from model evidence.
- Corrected LangChain native message, model-response and tool-output digest construction to use observed JSON/SDK model serialization instead of Python object string representations; added focused tests.

## [v0.4.0] — AI Systems Seven-Phase Roadmap completion

### Phase 7 - Comparative Validation Study

- Added `statewake.validation_study` with deterministic fixture-backed comparative validation for final-output-only, conventional-log, structured-trace, and StateWake-full baselines.
- Added five representative workloads: RAG answer, tool action, incident recovery, release verification, and human approval workflow.
- Added a deterministic fault catalog covering omitted evidence, malformed/stale evidence, changed identity, missing authorization, modified tool output, broken provenance, invalid state, partial workspace write, erased recovery history, and unsigned release evidence.
- Added aggregate metrics for verification coverage, fault detection rate, false-positive rate, and checkable property counts.
- Added JSON and Markdown study report rendering with explicit limitations; live AI calls, statistical superiority claims, human reconstruction timing, runtime overhead, and storage overhead remain outside this fixture harness.
- Added benchmark directory scaffolding, research documentation, unit tests, and workspace persistence tests for generated study reports.

### Phase 6 - Supply-Chain and Release Trust Evidence

- Added `statewake.release_trust` with digest-bound release-trust bundle models for artifacts, source identity, build provenance, tests, SBOMs, vulnerability scans, signatures, external provenance, limitations, and human release decisions.
- Added deterministic JSON persistence and tamper detection for release-trust bundles.
- Added a bridge from release-trust bundles into the existing `release_evidence_complete.v1` claim profile without replacing `release_proof_service`.
- Preserved the separation between verified release evidence and human publication approval; unsigned development releases must record an explicit limitation rather than a pass.
- Added regression tests for artifact digests, dependency-lock digests, SBOM tamper detection, false signature claims, human approval basis, profile consumption, and JSON round trips.
- Documented the Phase 6 release-trust evidence boundary in `docs/release/release-trust-evidence.md`.

### Phase 5 - First-Class Integrations

- Added `statewake.integrations` with thin producer adapters for OpenTelemetry GenAI, OpenAI Agents-style traces, LangChain-style callbacks, LlamaIndex-style retrieval/evaluator events, LangGraph-style runtime events, CI/CD evidence, and generic evaluator results.
- Added `ContractCaptureResult` and workspace persistence support for integration-emitted Phase 1 AI contracts.
- Added integration regression tests proving lightweight imports, event-to-contract mapping, profile evaluation compatibility, and explicit workspace persistence.
- Documented the Phase 5 dependency policy: no new hard framework dependency and no guessed optional SDK versions without compatibility testing.


### Phase 4 - Workspace Backup, Restore, and Migration Guarantees

- Added Phase 4 workspace backup and restore helpers that preserve the SQLite operational index, manifest, receipts, artifacts, and exports together.
- Added content-addressed payload integrity sweeps to detect modified or invalid artifact files.
- Added explicit workspace migration marker modules for the initial schema, AI-contract compatibility, and claim-profile-result compatibility without duplicating existing evidence tables.
- Updated the default workspace root to durable `data/statewake/` while preserving explicit test workspaces.
- Added regression coverage for default workspace durability, schema identity, backup/restore round trips, tampered backups, modified payloads, and Phase 2/3 evidence preservation.
- Documented backup, restore, and migration behavior in `docs/operations/workspace-backup-restore.md`.

### Phase 3 - Human Verification Reports

- Extended the existing reliability verification report contract instead of adding a duplicate report authority.
- Added reusable Markdown and JSON renderers under `statewake.reports`.
- Added explicit candidate identity, candidate digest, missing evidence, `UNRUN-ENV`, `UNKNOWN`, residual-risk, and human-decision sections.
- Added report redaction helpers that preserve payload digests while hiding sensitive fields.
- Added unit and workspace tests covering Phase 1 contracts, Phase 2 profile evaluation, and Phase 3 report rendering together.
- Documented verification reports in `docs/user-guide/verification-reports.md`.

### Phase 2 - Claim Profiles

- Added the Phase 2 built-in AI reliability claim-profile catalog with eight versioned profiles.
- Extended profile evaluation with Phase 2 decisions, missing-evidence reporting, caveats, and deterministic serialization.
- Added public profile listing through Python and the CLI, plus workspace persistence coverage for profile evaluation results.
- Documented the profile catalog in `docs/reference/claim-profiles.md`.

### Phase 1 - AI Evidence Contracts

- Added `statewake.ai_contracts` with deterministic, digest-bound contracts for prompts, model invocations, tool calls, retrieval, policies, evaluators, human approvals, and runtime traces.
- Added contract-to-`EvidenceItem` binding and explicit workspace persistence tests for serialized AI contract payloads.
- Documented the AI evidence contract boundary in `docs/architecture/ai-evidence-contracts.md`.

## Historical baseline — Persistence & Dataset Architecture completion

### Enhanced dependency and verification baseline

- Declared the implemented optional workspace adapters in `pyproject.toml` through the `workspace` extra: DuckDB, PyArrow, openpyxl, and SQLAlchemy.
- Synchronized `uv.lock` with the workspace adapter dependency set.
- Documented the workspace installation path and clarified which persistence/export capabilities remain standard-library based.
- Extended release verification to exercise the optional workspace dependency surface when those dependencies are available.
- Revalidated Tier 8 supply-chain provenance after the dependency declaration/lock update; the dependency-lock digest and candidate fingerprint are regenerated for the enhanced artifact.

The earlier persistence/dataset baseline completed the Persistence & Dataset Architecture through Tier 15. This is a backward-compatible minor capability release built on the v0.2.0 cybersecurity baseline.

### Included

- Workspace foundation, durable operational index, ingestion binding, and restart/recovery guarantees.
- Typed historical query surface and stable dataset projections.
- Parquet, CSV, XLSX, JSON, and portable bundle exports.
- Lifecycle, retention, integrity, and workspace verification.
- Analytical access over Parquet through the optional DuckDB adapter.
- Repository/backend abstraction.
- Production workspace operations, locking, diagnostics, storage reporting, and operational guidance.

The public API contract version remains `1`.

## [v0.2.0] — Cybersecurity capability completion

StateWake v0.2.0 completes the cybersecurity architecture through V3 Tier 15. This is a backward-compatible minor capability release.

### Included

- Security Assurance and Continuous Security Assurance.
- Recovery and Resilience Assurance.
- Trust-Domain and Anchor Assurance.
- Supply-Chain and Release Assurance.
- Evidence-Portability and Independent Verification Assurance.
- Assurance Operations and security decision automation.
- Identity-bound access and least privilege.
- Runtime and hostile-input containment.
- Data lifecycle and confidentiality protection.
- Security incident evidence and forensic continuity.
- Cryptographic longevity and trust migration.

The public API contract version remains `1`.

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

- Replaced generic dataclass metadata factories with explicitly typed string-to-string factories to prevent unknown-type propagation under strict mypy.
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
- Native Ruff, mypy, and PyNaCl remain environment-dependent verification gates when unavailable in an isolated sandbox.

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
## Native integration SDK import compatibility audit — 2026-09-23

- Updated OpenAI Agents and LangChain callback imports to the officially documented defining modules rather than assuming top-level re-exports.
- Added the LlamaIndex event-handler class identity required by the SDK, and stopped inventing missing LlamaIndex event timestamps.
- Preserved native LangGraph history and OpenTelemetry SDK imports where they match published APIs.
- Added real SDK import/instantiation smoke tests, corrected fake-module test fixtures, and stopped masking transitive import failures as missing SDK extras.
- Recorded unresolved optional-dependency lock and absent real SDK gates; candidate remains unpromoted.
## Native integration release and private-boundary review

- Added current-release native SDK compatibility jobs to release verification and publication; publication now depends on real SDK imports and native integration tests. Historical v0.2.0/v0.3.0 release records are not rewritten.
- Audited underscore-prefixed declarations across production source, scripts, tests, and config, documenting test-only private imports and unproven dead-code candidates.
- Recorded the review in `docs/verification/native-integration-release-and-private-boundary-audit.md`; this remains a development candidate until the integration dependency lock and live SDK gates pass.


### Follow-up: frozen end-to-end negative-trial corrections (development candidate)

- Permit separate captures within one run to have different observed times while preserving producer authority and record-identity checks.
- Route invalid-evidence Phase 7 fixtures to review/profile evaluation instead of aborting during construction; preserve the rejection of invalid accept decisions.
- Add out-of-order, producer-conflict, and benchmark-fixture regression tests; synthetic trial outputs remain separate from release identity.
