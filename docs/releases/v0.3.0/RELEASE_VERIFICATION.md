# StateWake v0.3.0 Release Verification

## Enhanced workspace dependency audit

The v0.3.0 implementation contains optional workspace adapters for:

- Parquet export/verification via `pyarrow==25.0.1`;
- read-only Parquet analytics via `duckdb==1.5.5`;
- XLSX export/verification via `openpyxl==3.1.5`;
- the alternative SQL repository backend via `sqlalchemy==2.0.54`.

These are now declared in `pyproject.toml` under the `workspace` optional extra, documented in the user/development guides, and exercised by a dedicated CI workspace-consumer job. Tier 8 verification was also strengthened to require every optional-extra dependency to be represented in `uv.lock`, not only core runtime dependencies.

### Current sandbox gate

The source and documentation changes are complete, but this isolated environment cannot regenerate `uv.lock`: outbound PyPI/DNS access is unavailable and the newly required workspace packages are not present in the local uv cache. Therefore the dependency-lock update is intentionally **not claimed as verified in this sandbox**. The previous `uv.lock` remains unchanged rather than being hand-edited or weakened with unverifiable package artifact metadata.

The enhanced candidate must not be treated as release-ready until `uv lock` is regenerated in a network-enabled dependency-complete environment, followed by `uv lock --check`, the workspace dependency matrix, full regression, and a new Tier 8 provenance record/fingerprint.

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

This sandbox was explicitly not allowed to install missing project dependencies. The full dependency-backed release gate therefore remains an external/local gate. In particular, the available environment does not contain the project's pinned PyNaCl runtime dependency, so tests requiring signed-key operations cannot be executed here. This is recorded as an environment limitation rather than converted into a pass claim.

Wheel/sdist creation and clean consumer installation are also left to the user's dependency-complete local environment.

## Publication boundary

This source tree records the release candidate and its evidence boundary. Publication, tagging, repository-server checks, and package-index upload remain separate authorized actions.

The v0.3.0 candidate includes the complete workspace implementation validated locally across its affected regression surface.
