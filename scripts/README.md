# StateWake Tooling

Project tooling is separated by responsibility:

- `common/` — shared non-runtime helpers
- `development/` — local setup and source-quality checks
- `testing/` — automated validation, chaos, property, and failure campaigns
- `integration/` — external integration runners
- `release/` — package, API, release-candidate, governance, and SDLC gates

Scripts are executable from the repository root and are designed to resolve the repository and source roots from their own location rather than the caller's current working directory.
