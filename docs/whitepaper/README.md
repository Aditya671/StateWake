# StateWake v0.5.0 technical white paper

- [Technical white paper (Markdown)](StateWake_Technical_White_Paper_v0.5.0.md)
- [Technical white paper (PDF)](StateWake_Technical_White_Paper_v0.5.0.pdf)

The Markdown and PDF editions are the supplied StateWake v0.5.0 technical white paper dated 5 October 2026. They are the current white-paper pair for this source line.

## Dependency errata

The paper describes DuckDB, PyArrow, openpyxl, and SQLAlchemy as a `workspace` optional extra. In this checkout those packages are standard runtime dependencies, while native framework SDKs remain optional extras. The current `pyproject.toml` is authoritative for dependency declarations. This errata applies to both the Markdown and PDF editions; the supplied white-paper contents are otherwise preserved unchanged.
