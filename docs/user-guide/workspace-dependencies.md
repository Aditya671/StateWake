# Workspace dependency model

StateWake keeps its reference persistence path dependency-light while making the richer v0.4.0 dataset/export adapters explicit and reproducible.

## Core runtime

The core package declares:

- PyNaCl for cryptographic signing/trust operations;
- OpenTelemetry API for the telemetry adapter boundary;
- filelock for filesystem coordination.

SQLite, CSV, JSON, and portable ZIP bundle operations use Python standard-library capabilities.

## Optional workspace extra

Install the complete workspace adapter surface with:

```bash
python -m pip install "statewake-ai[workspace]"
```

The extra declares these pinned packages:

| Capability | Package | Version |
|---|---|---:|
| Parquet export/verification | `pyarrow` | `25.0.1` |
| Read-only Parquet analytics | `duckdb` | `1.5.5` |
| XLSX export/verification | `openpyxl` | `3.1.5` |
| Alternative SQL repository backend | `sqlalchemy` | `2.0.54` |

The versions are part of the repository's locked dependency state in `uv.lock` and are therefore included in Tier 8 dependency provenance.

## Adapter boundaries

These packages remain optional rather than becoming mandatory core dependencies:

- SQLite remains the reference repository implementation.
- CSV and JSON exports do not require third-party packages.
- Parquet requires PyArrow only when Parquet operations are invoked.
- DuckDB is loaded lazily only for analytical SQL over exported Parquet datasets.
- XLSX requires openpyxl only when XLSX operations are invoked.
- SQLAlchemy is loaded lazily only when the alternative repository backend is constructed.

This preserves the lightweight core while making the implemented v0.4.0 workspace capabilities discoverable and installable as one coherent optional surface.
