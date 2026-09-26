# Workspace dependency model

StateWake installs its workspace adapters as standard runtime dependencies. Native framework SDK integrations are separately installable extras so applications do not receive framework upgrades they do not use. `pyproject.toml` is the install-policy authority and `uv.lock` records the repository development resolution.

## Installation

Install the base package to use the complete workspace adapter surface:

```bash
python -m pip install statewake-ai
```

The required runtime dependencies include:

| Capability | Package | Version |
|---|---|---:|
| Parquet export/verification | `pyarrow` | `25.0.1` |
| Read-only Parquet analytics | `duckdb` | `1.5.5` |
| XLSX export/verification | `openpyxl` | `3.1.5` |
| Alternative SQL repository backend | `sqlalchemy` | `2.0.54` |

Native SDK adapters are requested separately, for example `statewake-ai[integrations-langchain]`, or together with `statewake-ai[integrations]`. These extras are not required for workspace persistence/export functionality.

The complete dependency set and supported version bounds are declared in `pyproject.toml`. The resolved versions are recorded in `uv.lock` and included in Tier 8 dependency provenance. SQLite, CSV, JSON, and portable ZIP bundle operations use Python standard-library capabilities.

## Adapter boundaries

These packages remain optional rather than becoming mandatory core dependencies:

- SQLite remains the reference repository implementation.
- CSV and JSON exports do not require third-party packages.
- Parquet requires PyArrow only when Parquet operations are invoked.
- DuckDB is loaded lazily only for analytical SQL over exported Parquet datasets.
- XLSX requires openpyxl only when XLSX operations are invoked.
- SQLAlchemy is loaded lazily only when the alternative repository backend is constructed.

This preserves the lightweight core while making the implemented v0.4.0 workspace capabilities discoverable and installable as one coherent optional surface.
