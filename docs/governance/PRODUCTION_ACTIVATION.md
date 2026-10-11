# Production Activation

## Purpose

This document separates source-level release evidence from live GitHub/PyPI activation. A locally verified source artifact is not a production deployment, GitHub ruleset change, protected-environment approval, tag, or package publication.

## Current boundary

- Package source version is `v0.5.1`; this exact successor version has been explicitly approved under `VERSIONING.md`.
- GitHub already has an immutable historical `v0.5.0` tag/release at a different source revision. Do not move, delete, or reuse that tag for the current candidate.
- The approved successor is `v0.5.1` (PATCH) because the post-v0.5.0 work is backward-compatible release/CI hardening rather than a public API, CLI, HTTP, or serialization break.
- Exact-version approval is complete for `v0.5.1`; tag creation, GitHub Release creation, TestPyPI/PyPI publication, and registry reconciliation remain separate authorized actions.

## Required live GitHub activation sequence

1. Introduce the verified source through the normal protected pull-request path.
2. Ensure the `main` branch ruleset requires the stable CI contexts `quality`, `tests-linux`, `portability-windows`, and `package`.
3. Run those four contexts on the latest candidate commit and require successful results from that exact revision.
4. Run `Release Verification` against the same revision. This is the authoritative proof for the pinned uv/build/package path and remains required after the approved v0.5.1 version change.
5. Confirm the protected GitHub Environments `testpypi` and `pypi` exist and have the intended reviewers/branch restrictions.
6. Confirm TestPyPI and PyPI Trusted Publisher records point to `.github/workflows/python-publish.yml` and the matching GitHub environment.
7. With v0.5.1 approved, keep all synchronized version surfaces, release identity, and security evidence aligned and run ordinary CI again on the versioned candidate.
8. Create the new immutable `v0.5.1` tag only after the approved candidate passes the required checks.
9. Require the tag-triggered `Release Verification` run to succeed for the exact tag commit.
10. Use TestPyPI rehearsal first when desired, then create the production GitHub Release for the approved tag. The publication workflow resolves the exact successful Release Verification run, prepares authorization outside the OIDC job, publishes in the protected environment, and reconciles public registry bytes afterward.

## Stable required checks

The branch ruleset should require these job names exactly:

- `quality`
- `tests-linux`
- `portability-windows`
- `package`

Do not require expanded matrix labels or transient step names. Required checks must be produced by an eligible event such as `pull_request` or `push` on the latest candidate revision.

## Failure handling

- A missing or unreadable governance control is a release blocker, not a reason to bypass the verifier.
- A failed required CI context must be fixed or rerun only after the underlying cause is understood.
- A failed Release Verification run must not be substituted with a different source revision.
- A registry duplicate/version conflict must fail loudly for production PyPI. Do not reuse an existing version to make publication pass.
- Protected-environment approval and OIDC authentication are live platform controls and cannot be established by local source tests.

## Evidence to retain

For the approved release candidate retain: source revision, candidate/source-tree identity, required CI run URLs, Release Verification run ID, distribution SHA-256 values, release-candidate evidence, publication basis, authorization/permit evidence, registry receipt, lifecycle observation, SBOM, dependency audit, and provenance.
