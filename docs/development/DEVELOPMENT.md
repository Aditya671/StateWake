# Development

## Prerequisites

- Python 3.11–3.13 (`>=3.11,<3.14`)
- uv
- Git

StateWake uses a `src/` package layout. Runtime dependencies and optional native-SDK integration extras are declared in `pyproject.toml`; the exact reproducible dependency graph is committed in `uv.lock`.

## Setup

Install the locked development environment with all maintained integration extras:

```bash
uv sync --locked --group dev --extra integrations
```

For work that does not exercise optional native SDK integrations, the base development environment is sufficient:

```bash
uv sync --locked --group dev
```

## Run

```bash
uv run statewake --help
uv run statewake version
```

## Tests

```bash
uv run pytest
```

Focused suites may be run by path while developing, but the release gate uses the repository's canonical SDLC/release commands rather than a reduced substitute.

## OpenTelemetry adapter

OpenTelemetry API support is installed with StateWake. The host application remains responsible for configuring its `TracerProvider`, span processors, exporters, and resources.

## Build

```bash
uv build --no-sources
```

## Quality tooling

Ruff and mypy are repository quality gates. Their configuration is stored in `pyproject.toml`; executable Python surfaces under `src/`, `tests/`, `scripts/`, and `examples/` are covered by the maintained checks.

```bash
make check
make prepare-validation
make sdlc-check
```

Before a release candidate is evaluated, use the release profile and package verifiers documented under `docs/governance/`.

## Guiding rule

Before adding an LLM-driven component, ask whether the problem can be solved more reliably with a deterministic mechanism such as validation, hashing, comparison, rules, or replay.
