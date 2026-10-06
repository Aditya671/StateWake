"""Authoritative current-project release-input selection.

The runnable source and its active verification inputs affect candidate identity;
historical research, prior releases and generated artifacts do not. The built wheel
is verified separately and must never be limited by this source selector.
"""

from __future__ import annotations

from pathlib import Path

from scripts.common.project_metadata import load_project_metadata

CURRENT_TOP_LEVEL = frozenset(
    {
        ".gitattributes",
        ".gitignore",
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
        "scripts",
        "tests",
        "ui",
        "docs/adr",
        "docs/architecture",
        "docs/development",
        "examples",
        "docs/governance",
        "docs/integrations",
        "docs/operations",
        "docs/reference",
        "docs/release",
        "docs/security",
        "docs/specifications",
        "docs/testing",
        "docs/user-guide",
        "docs/whitepaper",
        "benchmarks/faults",
        "benchmarks/statewake_enabled",
        "benchmarks/baselines",
        ".github/workflows",
    }
)
CURRENT_RELEASE_NOTES = load_project_metadata(
    Path(__file__).resolve().parents[2]
).current_release_notes_relative.as_posix()

CURRENT_DOCS = frozenset(
    {
        "docs/README.md",
        "docs/releases/README.md",
        CURRENT_RELEASE_NOTES,
        "docs/SDLC.md",
        "docs/QUALITY_GATES.md",
        "docs/DEFINITION_OF_DONE.md",
        "data/README.md",
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
        "node_modules",
        ".next",
        "coverage",
    }
)


def is_ignored_repository_path(relative: Path) -> bool:
    """Return whether a path belongs to local/generated repository state.

    The release and repository-structure authorities share this boundary so
    local environments (for example ``.venv`` or ``node_modules``) never
    become release inputs or structural failures merely because they exist in
    a developer checkout.
    """
    if relative.is_absolute() or ".." in relative.parts:
        return True
    if not relative.parts or any(part in GENERATED_PARTS for part in relative.parts):
        return True
    return relative.name.endswith(".tsbuildinfo")


def repository_files(root: Path) -> tuple[Path, ...]:
    """Enumerate maintained repository files while pruning local/generated trees."""
    pending = [root]
    files: list[Path] = []
    while pending:
        directory = pending.pop()
        for path in directory.iterdir():
            if path.is_symlink():
                continue
            relative = path.relative_to(root)
            if is_ignored_repository_path(relative):
                continue
            if path.is_dir():
                pending.append(path)
            elif path.is_file():
                files.append(path)
    return tuple(sorted(files, key=lambda path: path.relative_to(root).as_posix()))


def is_release_input(relative: Path) -> bool:
    """Select maintained release inputs, excluding ancillary and generated files."""
    if is_ignored_repository_path(relative):
        return False
    path = relative.as_posix()
    if path in CURRENT_TOP_LEVEL or path in CURRENT_DOCS:
        return True
    return any(path.startswith(prefix + "/") for prefix in CURRENT_DIRECTORIES)


def release_input_files(root: Path) -> tuple[Path, ...]:
    """Enumerate release inputs without following symlinked files or directories."""
    return tuple(
        path
        for path in repository_files(root)
        if is_release_input(path.relative_to(root))
    )
