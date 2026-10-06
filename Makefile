.PHONY: sync test lint format format-check typecheck check prepare-validation sdlc-check sdlc-release build

sync:
	uv sync --locked --group dev --extra integrations

test:
	uv run --no-sync pytest

lint:
	uv run --no-sync ruff check src tests scripts examples

format:
	uv run --no-sync ruff format src tests scripts examples

format-check:
	uv run --no-sync ruff format --check src tests scripts examples

typecheck:
	uv run --no-sync mypy

check: lint format-check typecheck test

build:
	uv build --no-sources

prepare-validation:
	uv run --no-sync python scripts/release/prepare_sdlc_validation.py

sdlc-check:
	uv run --no-sync python scripts/release/run_sdlc_validation.py --profile check

sdlc-release:
	uv run --no-sync python scripts/release/run_sdlc_validation.py --profile release
