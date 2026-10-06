"""Repository ignore-policy regression tests."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GITIGNORE = ROOT / ".gitignore"


def _rules() -> set[str]:
    """Return normalized non-comment ignore rules."""
    return {
        line.strip()
        for line in GITIGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_gitignore_covers_statewake_generated_surfaces() -> None:
    """Ignore generated Python, UI, workspace, validation, and runtime outputs."""
    rules = _rules()
    required = {
        ".venv/",
        "__pycache__/",
        ".pytest_cache/",
        ".mypy_cache/",
        ".ruff_cache/",
        ".coverage",
        "coverage/",
        "htmlcov/",
        "build/",
        "dist/",
        "/verification/",
        "/data/statewake.db",
        "/data/statewake.db-wal",
        "/data/statewake.db-shm",
        "/data/statewake.db-journal",
        "/data/statewake/",
        "/artifacts/",
        "/receipts/",
        "/proofs/",
        "/exports/",
        "/locks/",
        "ui/node_modules/",
        "ui/.next/",
        "ui/out/",
        "ui/coverage/",
        "*.tsbuildinfo",
        ".env",
        ".env.*",
        "*.log",
        "*.tmp",
        ".DS_Store",
        "Thumbs.db",
    }
    assert required <= rules


def test_gitignore_keeps_canonical_dependency_and_identity_inputs_trackable() -> None:
    """Never ignore maintained lockfiles or StateWake candidate identity files."""
    rules = _rules()
    forbidden = {
        "*.lock",
        "uv.lock",
        "package-lock.json",
        "verification_manifest.txt",
        "candidate-fingerprint.txt",
        "*.jsonl",
        "data/",
        "tests/fixtures/",
        "benchmarks/",
    }
    assert rules.isdisjoint(forbidden)
    assert "!ui/package-lock.json" in rules


def test_gitignore_allows_shareable_environment_templates() -> None:
    """Allow sanitized environment templates while excluding real local env files."""
    rules = _rules()
    assert {"!.env.example", "!.env.sample", "!.env.template"} <= rules
