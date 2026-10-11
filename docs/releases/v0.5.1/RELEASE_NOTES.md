# StateWake v0.5.1 Release Notes

**Status:** approved source release candidate / not yet published to PyPI. Version approval does not itself authorize tagging, GitHub Release creation, TestPyPI/PyPI publication, or registry reconciliation.

## Release lineage

- Current published Production/Stable PyPI baseline: `v0.4.1`.
- Historical GitHub operational-trust release/tag: `v0.5.0` at commit `e26db67c3e590012eae8b5f705a8b6fcc8039101`.
- Current approved candidate: `v0.5.1`. The v0.5.0 tag is never moved or reused.

Because v0.5.0 was not the current PyPI baseline, the v0.5.1 package candidate carries the cumulative operational-trust capability line plus the post-tag hardening below.

## Operational-trust capability carried forward

- Privacy-aware evidence admission and evidence-governance enforcement.
- Historical signing-key/trust-state interpretation.
- Append-only human approval lifecycle with active/revoked/superseded projection.
- Exact release-publication basis and execution permits bound to source, verification evidence, target registry, and distribution digests.
- PyPI/TestPyPI registry publication receipts, independent byte read-back, and continuing availability/yank lifecycle history.
- Native-host qualification across OpenAI Agents, LangChain, LangGraph, LlamaIndex, and OpenTelemetry while preserving host-owned truth as a separate evidence stream.
- Bounded read/review/approval and optional UI surfaces without making StateWake a second identity, execution, or publication authority.

## v0.5.1 patch hardening

### Test and repository cleanup

- Removed brittle workflow-source locks, one-time compatibility assertions, duplicate release/SDLC choreography tests, and pytest wrappers around standalone repository/product verifiers while retaining behavioral, security, persistence, portability, tamper, archive/path, and public-API regressions.
- Moved static repository hygiene checks into the deterministic repository-structure verifier instead of scattering them through pytest.
- Removed generated/cache/build/runtime state from deliverable artifacts and kept release-input enumeration explicitly bounded to maintained source.

### Read-only SDLC and security boundaries

- Made SDLC verification read-only: verification no longer synchronizes dependencies, promotes security baselines, or refreshes release identity implicitly.
- Kept security-baseline promotion and release-identity refresh as explicit maintenance actions with auditable re-verification.
- Verified exact locked validation dependency versions rather than treating package presence as sufficient.

### Cross-platform reliability

- Corrected Windows path/byte-accounting and descriptor-I/O behavior without weakening Linux/POSIX hardening.
- Removed real-time deadline sleeps in favor of deterministic deadline state.
- Preserved corruption/WAL, persistence, locking, archive/path traversal, symlink, attestation, signature, and tamper regressions.

### CI, build, and publication orchestration

- Replaced the duplicated source mega-matrix with four stable required checks: `quality`, `tests-linux`, `portability-windows`, and `package`.
- Pinned required runner images and third-party actions, pinned uv, and added controlled Dependabot streams rather than relying on silent `latest` drift.
- Made Release Verification the sole distribution-build authority and made publication consume immutable artifacts from the exact successful verification run.
- Added bounded Release Verification resolution to eliminate release-event races.
- Consolidated publication into resolve → prepare → minimal protected OIDC publish → reconcile, keeping repository code out of the privileged uploader job.
- Added bounded timeouts and explicit production-activation governance for CI, protected environments, tag creation, TestPyPI rehearsal, PyPI publication, and registry reconciliation.

### Version and release identity

- Approved and synchronized package version `0.5.1` across project metadata, import package, lockfile, public API/reference manifests, release notes, governance, README/UI source-line labels, and current documentation.
- Preserved public API contract version `1`; no incompatible public API, HTTP, data-contract, or serialization change is introduced.
- Made registry HTTP User-Agent identity derive from `statewake.__version__` instead of retaining a stale hard-coded release-line value.
- Preserved the historical v0.5.0 GitHub tag/release and v0.5.0 white paper as immutable provenance rather than rewriting them to v0.5.1.

## Publication boundary

A successful local candidate is not publication authorization. Before production publication, the exact v0.5.1 GitHub candidate must pass the four stable required checks, Release Verification must succeed for the exact tag commit, protected `testpypi`/`pypi` environments and Trusted Publisher configuration must be confirmed, and the existing publication authorization/permit and registry reconciliation lifecycle must complete.
