# StateWake v0.3.0 Release Verification

## Enhanced workspace dependency audit

The v0.3.0 implementation contains optional workspace adapters for:

- Parquet export/verification via `pyarrow==25.0.1`;
- read-only Parquet analytics via `duckdb==1.5.5`;
- XLSX export/verification via `openpyxl==3.1.5`;
- the alternative SQL repository backend via `sqlalchemy==2.0.54`.

These are now declared in `pyproject.toml` under the `workspace` optional extra, documented in the user/development guides, and exercised by a dedicated CI workspace-consumer job. Tier 8 verification was also strengthened to require every optional-extra dependency to be represented in `uv.lock`, not only core runtime dependencies.

### Historical sandbox gate (v0.3.0 verification snapshot)

At the time of this isolated v0.3.0 verification, the environment could not regenerate `uv.lock`: outbound PyPI/DNS access was unavailable and the newly required workspace packages were not present in the local uv cache. The dependency-lock update was therefore **not claimed as verified in that snapshot**. The previous `uv.lock` was left unchanged rather than being hand-edited or weakened with unverifiable package artifact metadata.

That v0.3.0 snapshot required a refreshed lock, `uv lock --check`, the workspace dependency matrix, full regression, and a new Tier 8 provenance record/fingerprint before its promotion gates could be considered complete.

## Candidate identity

- Distribution: `statewake-ai`
- Import package: `statewake`
- Package version: `0.3.0`
- Public API contract version: `1`
- Python baseline: `>=3.11,<3.14`

## Verified locally

- Package/import/version identity is synchronized.
- `uv.lock --check` passes without changing dependencies.
- Compatibility fixtures pass.
- Product-experience verification passes.
- Source compilation passes.
- The focused release/security regression suites pass in the available environment.
- The source-tree verification manifest and candidate fingerprint are synchronized.

## Environment limitation

The v0.3.0 verification environment did not install missing project dependencies. In particular, it lacked the pinned PyNaCl runtime dependency, so tests requiring signed-key operations could not be executed in that snapshot. This is recorded as an environment limitation rather than converted into a pass claim.

Wheel/sdist creation and clean consumer installation are also left to the user's dependency-complete local environment.

## Publication boundary

This source tree records the release candidate and its evidence boundary. Publication, tagging, repository-server checks, and package-index upload remain separate authorized actions.

The v0.3.0 candidate includes the complete workspace implementation validated locally across its affected regression surface.
