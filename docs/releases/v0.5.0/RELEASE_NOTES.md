# StateWake v0.5.0 Release Notes

**Status:** source candidate / unreleased. This document does not authorize publication and does not claim release readiness.

## Changes since published v0.4.1

- Added canonical human-approval revocation and supersession lifecycle evidence, with active/revoked/superseded projection and fresh release-proof reconciliation limited to active approval evidence.
- Added canonical release-publication authorization and execution permits bound to exact source, verification, target-registry, and distribution digests.
- Added canonical PyPI/TestPyPI publication receipts with independent registry read-back of the exact public distribution bytes.
- Added digest-chained registry lifecycle observations for available, yanked, partially available, and unavailable release states, including post-publication reconciliation.
- Added independent-oracle real-system native-host qualification across OpenAI Agents, LangChain, LangGraph, LlamaIndex, and OpenTelemetry using credential-free host exercises, separate host/StateWake ledgers, durable read-back, and synthetic-secret leakage checks.
- Performed production cleanup for the v0.5.0 source line: synchronized package/version references, removed unused TestPyPI resolver configuration and nonexistent historical-directory tool exclusions, pinned the optional UI's direct dependencies to versions evidenced by the supplied UI package bundle, and removed the empty generated-verification directory from the source artifact.
- Refreshed the root repository README for the complete v0.5.0 source surface, removed the competing `.github/README.md`, and replaced obsolete v0.1.1 installation guidance with current public-release, source-candidate, and integration-extra installation paths.
- Reworked release/verification metadata discovery so the current version, release-note path, distribution/import package, CLI target, package root, lock-project match, GitHub repository identity, and default branch are derived from canonical project/live metadata rather than duplicated release-specific literals.
- Normalized repository structure without changing runtime architecture: executable examples are separated from documentation, repository path helpers live with maintenance tooling, workspace operations guides are grouped under operations, generated runtime data is kept outside source, old validation snapshots are isolated with their historical release, and active development-sequence filenames were renamed to purpose-based names while frozen study/release evidence was preserved.
- Corrected repository-governance indexing and local documentation links, strengthened structural regression checks for retired/misplaced paths, and aligned local sync/build guidance with locked dependency resolution and source-independent distribution builds.
- Corrected strict frontend TypeScript production-build failures in claim comparison selection and Axios workspace-operation request typing while retaining `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`.
- Corrected the attestation-trust UI regression to test for raw cryptographic fields precisely while preserving safe signed-binding metadata in the read-only projection.
- Corrected the Next.js App Router/Ant Design server-component boundary by using a dedicated client-side Typography wrapper for server-rendered pages, and pinned Turbopack to the UI package root to prevent unrelated repository lockfiles from affecting workspace inference.
- Corrected repository verification to prune local/generated dependency trees before structural and release-input enumeration, preventing `.venv` or frontend dependency internals from being mistaken for maintained StateWake source.
- Corrected Windows mypy portability in attestation trust-history persistence while retaining POSIX file-descriptor permission hardening.
- Corrected Windows reliability-attestation persistence/readback so JSONL descriptor I/O is binary, snapshot byte counts are derived from exact physical bytes, and LF/CRLF regression fixtures are constructed byte-for-byte without platform newline translation.

### Windows validation and SDLC preflight

- StateWake security-audit persistence/snapshot reads use binary descriptor I/O so Windows CRT newline translation cannot change physical-byte accounting.
- POSIX `0600` assertions are enforced only where POSIX mode bits are meaningful; Windows deployment ACL enforcement remains host-owned.
- SDLC validation begins with `prepare_sdlc_validation.py`, which refreshes release identity, verifies the Python lock and security-assurance state, and deliberately does not auto-promote the security baseline or rewrite dependency locks/source.
- The current white-paper boundary is derived from the configured project version rather than a hard-coded v0.5.0/v0.4.0 pair.

## Preserved boundaries

- Public API contract version remains `1`.
- Published v0.4.1 release records remain historical evidence and are not rewritten.
- Historical v0.4.1 registry/publication fixtures remain valid compatibility inputs.
- External public-host qualification and publication authorization remain separate gates; this source-version update does not satisfy them.

## Documentation refresh

- The repository white-paper boundary now contains the supplied StateWake v0.5.0 Markdown and PDF editions; the superseded v0.4.0 white-paper files and v0.4.0-only grounding map were removed from `docs/whitepaper/`.

