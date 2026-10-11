.PHONY: sync test lint format format-check typecheck check lock-check \
	refresh-release-identity verify-release-identity verify-security-assurance \
	promote-security-baseline sdlc-check sdlc-release build

sync:
	uv sync --locked --group dev --extra integrations

lock-check:
	uv lock --check

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

check: lock-check lint format-check typecheck test

refresh-release-identity:
	uv run --no-sync python scripts/release/refresh_release_identity.py

verify-release-identity:
	uv run --no-sync python scripts/release/verify_release_identity.py

verify-security-assurance:
	uv run --no-sync python scripts/security/verify_continuous_security_assurance.py

promote-security-baseline:
	uv run --no-sync python scripts/security/promote_security_assurance_baseline.py

sdlc-check:
	uv run --no-sync python scripts/release/run_sdlc_validation.py --profile check

sdlc-release:
	uv run --no-sync python scripts/release/run_sdlc_validation.py --profile release

build:
	uv build --no-sources
