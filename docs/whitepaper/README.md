# StateWake v0.4.0 technical white paper

- [Technical white paper (Markdown)](StateWake_Technical_White_Paper_v0.4.0.md)
- [Technical white paper (PDF)](StateWake_Technical_White_Paper_v0.4.0.pdf)
- [Technical grounding and source map](Technical_Grounding_and_Source_Map.md)

The paper and companion map are preserved as supplied, dated 21 September 2026. The paper describes the implementation and evidence available at that time; its validation counts are historical. The current source version is v0.4.1; the dated paper remains a v0.4.0 source record. For current installation and release status, use [the package metadata](../../pyproject.toml), [workspace dependencies](../user-guide/workspace-dependencies.md), and [release information](../user-guide/release.md).

## Dependency errata

The paper's sections 5.3 and 7 describe a `workspace` optional extra. In this checkout, DuckDB, PyArrow, openpyxl, and SQLAlchemy are standard runtime dependencies. Native framework SDKs remain optional extras. The current `pyproject.toml` is authoritative for both dependency groups. This errata applies to the Markdown and PDF editions.
