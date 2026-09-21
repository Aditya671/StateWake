# Development

## Prerequisites

- Python 3.11–3.13
- uv
- Git

The project uses a `src/` package layout and a dependency-light runtime core. uv manages the project and lockfile. OpenTelemetry API support is a declared adapter-layer dependency; the domain core remains framework-neutral. The v0.3.0 workspace adapters are exposed through the optional `workspace` extra and cover PyArrow/Parquet, DuckDB analytical access, openpyxl/XLSX export, and SQLAlchemy-backed repository access.

## Setup

```bash
uv sync
```

## Run

```bash
uv run statewake --help
uv run statewake version
uv run statewake --help
```

## Tests

The normal project environment installs the declared runtime dependencies, including the OpenTelemetry API and cryptographic verification support. To exercise every implemented workspace adapter locally, install the `workspace` extra as well.

```bash
uv run python -m unittest discover -s tests -p 'test_*.py'
```

## OpenTelemetry adapter

OpenTelemetry API support is installed with StateWake. The host application remains responsible for configuring its `TracerProvider`, span processors, exporters, and resources.

## Build

```bash
uv build
```

## Quality tooling

Ruff and mypy are repository quality gates. Their configuration is stored in
`pyproject.toml`; mypy checks active Python code under `src/`, `tests/`,
`scripts/`, and `docs/`, with fixture-friendly overrides for tests.

## Guiding rule

Before adding an LLM-driven component, ask whether the problem can be solved more reliably with a deterministic mechanism such as validation, hashing, comparison, rules, or replay.
