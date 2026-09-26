# StateWake v0.3.0

## Release boundary

v0.3.0 is the completed Persistence & Dataset Architecture release, adding the canonical StateWake workspace from Tier 1 through Tier 15.

## Included capabilities

- Workspace foundation and durable operational index.
- Canonical ingestion binding and restart/recovery guarantees.
- Typed deterministic historical query surface.
- Stable dataset projections.
- Parquet, CSV, and XLSX export adapters.
- JSON and portable dataset bundle export.
- Lifecycle and retention orchestration.
- Workspace integrity and verification.
- Analytical access over Parquet through the optional DuckDB adapter.
- Backend abstraction through the existing repository protocol.
- Production workspace operations, locking, diagnostics, storage reporting, and operational guidance.

The release builds on the v0.2.0 cybersecurity baseline and preserves the public API contract version `1`.
