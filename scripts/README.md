# StateWake Tooling

Project tooling is separated by responsibility:

- `common/` — shared non-runtime helpers
- `development/` — local setup and source-quality checks
- `testing/` — automated validation, independent-oracle system trials, chaos, property, and failure campaigns
- `integration/` — external integration runners
- `release/` — package, API, release-candidate, governance, and SDLC gates

Scripts are executable from the repository root and are designed to resolve the repository and source roots from their own location rather than the caller's current working directory.

## Native SDK qualification

`scripts/testing/run_public_trial_regressions.py --mode qualification` is the single repository coordinator for native OpenAI Agents, LangChain, LangGraph, and LlamaIndex qualification. Use `--output` for the machine-readable evidence record and `--report` for the bounded Markdown summary. The coordinator reads integration requirements from `pyproject.toml`; it does not install SDKs or call live model services.
