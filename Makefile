.PHONY: sync test lint format format-check typecheck check sdlc-check sdlc-release build

sync:
	uv sync

test:
	uv run pytest

lint:
	uvx ruff@0.16.5 check src tests scripts

format:
	uvx ruff@0.16.5 format src tests scripts

format-check:
	uvx ruff@0.16.5 format --check src tests scripts

typecheck:
	uv run mypy

check: lint format-check typecheck test

build:
	uv build


sdlc-check:
	uv run python scripts/release/run_sdlc_validation.py --profile check

sdlc-release:
	uv run python scripts/release/run_sdlc_validation.py --profile release
