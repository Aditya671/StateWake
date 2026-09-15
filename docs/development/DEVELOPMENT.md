# Development

## Prerequisites

- Python 3.11–3.13
- uv
- Git

The project uses a `src/` package layout and a standard-library runtime core. uv manages the project and lockfile. OpenTelemetry API support is a declared adapter-layer dependency; the domain core remains framework-neutral.

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

The normal project environment installs the declared runtime dependencies, including the OpenTelemetry API and cryptographic verification support.

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

Ruff and Pyright are repository quality gates. Ruff configuration is stored in pyproject.toml and Pyright/Pylance strict mode is configured for the active src/ tree.

## Guiding rule

Before adding an LLM-driven component, ask whether the problem can be solved more reliably with a deterministic mechanism such as validation, hashing, comparison, rules, or replay.
