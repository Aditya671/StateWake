"""Authoritative current-project release-input selection.

The runnable source and its active verification inputs affect candidate identity;
historical research, prior releases and generated artifacts do not. The built wheel
is verified separately and must never be limited by this source selector.
"""

from __future__ import annotations

from pathlib import Path

CURRENT_TOP_LEVEL = frozenset(
    {
        ".gitattributes",
        ".editorconfig",
        ".pre-commit-config.yaml",
        ".python-version",
        "CHANGELOG.md",
        "CONTRIBUTING.md",
        "LICENSE",
        "Makefile",
        "README.md",
        "SECURITY.md",
        "THIRD_PARTY_NOTICES.md",
        "pyproject.toml",
        "uv.lock",
    }
)
CURRENT_DIRECTORIES = frozenset(
    {
        "src",
        "config",
        "scripts",
        "tests",
        "docs/adr",
        "docs/architecture",
        "docs/development",
        "docs/examples",
        "docs/governance",
        "docs/integrations",
        "docs/operations",
        "docs/reference",
        "docs/release",
        "docs/security",
        "docs/specifications",
        "docs/testing",
        "docs/user-guide",
        "benchmarks/faults",
        "benchmarks/statewake_enabled",
        "benchmarks/baselines",
        ".github/workflows",
    }
)
CURRENT_DOCS = frozenset(
    {
        "docs/README.md",
        "docs/SDLC.md",
        "docs/QUALITY_GATES.md",
        "docs/DEFINITION_OF_DONE.md",
        "docs/workspace-backend-migration.md",
        "docs/workspace-production-operations.md",
    }
)
GENERATED_PARTS = frozenset(
    {
        ".git",
        ".venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "dist",
        "build",
    }
)


def is_release_input(relative: Path) -> bool:
    """Select maintained release inputs, excluding ancillary and generated files."""
    if relative.is_absolute() or ".." in relative.parts:
        return False
    path = relative.as_posix()
    if not relative.parts or any(part in GENERATED_PARTS for part in relative.parts):
        return False
    if path in CURRENT_TOP_LEVEL or path in CURRENT_DOCS:
        return True
    return any(path.startswith(prefix + "/") for prefix in CURRENT_DIRECTORIES)


def release_input_files(root: Path) -> tuple[Path, ...]:
    """Enumerate release inputs without following symlinked files or directories."""
    return tuple(
        sorted(
            (
                path
                for path in root.rglob("*")
                if path.is_file()
                and not path.is_symlink()
                and is_release_input(path.relative_to(root))
            ),
            key=lambda path: path.relative_to(root).as_posix(),
        )
    )
