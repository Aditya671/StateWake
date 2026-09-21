# StateWake v0.1.1 Production/Stable Release Candidate Verification

## Scope

This artifact promotes the verified StateWake `v0.1.0` public package baseline to `v0.1.1` with the PyPI classifier `Development Status :: 5 - Production/Stable`. No intentional public API or data-contract break was introduced.

## Verified in this sandbox

- `pyproject.toml` project version = `0.1.1`.
- `statewake.__version__` source declaration = `0.1.1`.
- `uv.lock` project version = `0.1.1` and `uv lock --check` passed.
- Public API contract version remains `1`.
- Active API contract package version = `0.1.1`.
- Production/Stable PyPI classifier is present in built wheel metadata.
- Repository source/test/script/config trees compile successfully with Python 3.13.
- Repository structure verification passed.
- CLI surface verification passed (21 supported commands).
- Product-experience verification passed (required documentation and golden examples).
- Offline wheel and sdist build completed successfully.
- Package-boundary verification passed for the built wheel.
- Distribution SHA-256 checksums are recorded in `DISTRIBUTION-SHA256SUMS.txt`.

## Environment-limited gates

The sandbox cannot complete the dependency-backed Ruff, mypy, and full pytest gates because the isolated environment does not contain the project's pinned development/runtime dependencies and outbound package-index DNS/network access is unavailable. An attempted `uv run` synchronization failed while resolving `iniconfig==2.3.0` from `files.pythonhosted.org`.

A clean wheel installation was also performed with `--no-deps`; wheel installation itself succeeded, but importing `statewake` in that dependency-free environment failed at the expected missing runtime dependency boundary (`filelock`). This is an environment limitation, not evidence of a package metadata defect.

Repository-governance verification additionally requires a GitHub governance token and was not executed against GitHub from this artifact-generation sandbox.

Therefore this artifact is a **verified release candidate**, not a claim that every CI/repository-server release gate was re-executed here.

## Required final gates before manual publication

1. Run the repository's pinned Ruff format/check gates.
2. Run pinned mypy strict analysis.
3. Run the complete pytest suite.
4. Run the GitHub Actions release-verification workflow against the exact pushed tree.
5. Confirm the GitHub release/tag is `v0.1.1` and that the production PyPI workflow is triggered by a published GitHub Release.
6. Verify the published PyPI artifact checksum against `DISTRIBUTION-SHA256SUMS.txt`.

## Manual GitHub commit suggestion

`release: promote StateWake to v0.1.1 Production/Stable`
