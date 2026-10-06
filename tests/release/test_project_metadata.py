"""Regression tests for dynamic release-sensitive project metadata."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.common.project_metadata import ProjectMetadataError, load_project_metadata


def _write_project(
    root: Path,
    *,
    version: str = "9.8.7",
    module_name: str = "examplepkg",
    module_root: str = "python-src",
    repository: str = "https://github.com/example-org/example-repo",
) -> None:
    """Write a minimal project configuration used by metadata tests."""
    (root / "pyproject.toml").write_text(
        f"""
[project]
name = "example-distribution"
version = "{version}"

[project.scripts]
{module_name} = "{module_name}.cli:main"

[project.urls]
Repository = "{repository}"

[tool.uv.build-backend]
module-name = "{module_name}"
module-root = "{module_root}"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_release_sensitive_paths_follow_pyproject_version(tmp_path: Path) -> None:
    """Changing project version must automatically change current release paths."""
    _write_project(tmp_path, version="9.8.7")
    metadata = load_project_metadata(tmp_path)

    assert metadata.version == "9.8.7"
    assert metadata.current_release_notes_relative == Path(
        "docs/releases/v9.8.7/RELEASE_NOTES.md"
    )


def test_package_and_cli_discovery_follow_build_metadata(tmp_path: Path) -> None:
    """Package discovery must come from the configured build backend and scripts."""
    _write_project(tmp_path, module_name="renamedpkg", module_root="lib")
    metadata = load_project_metadata(tmp_path)

    assert metadata.package_init_relative == Path("lib/renamedpkg/__init__.py")
    assert metadata.cli_name == "renamedpkg"
    assert metadata.cli_target == "renamedpkg.cli:main"
    assert metadata.cli_module == "renamedpkg.cli"


def test_github_repository_slug_is_derived_from_project_url(tmp_path: Path) -> None:
    """Governance verification must not hard-code repository owner/name."""
    _write_project(tmp_path, repository="https://github.com/acme/widgets.git")
    metadata = load_project_metadata(tmp_path)

    assert metadata.github_repository == ("acme", "widgets")


def test_non_github_repository_is_rejected_only_by_github_consumer(
    tmp_path: Path,
) -> None:
    """General metadata remains usable while GitHub-specific parsing fails closed."""
    _write_project(tmp_path, repository="https://example.test/acme/widgets")
    metadata = load_project_metadata(tmp_path)

    assert metadata.version == "9.8.7"
    with pytest.raises(ProjectMetadataError):
        _ = metadata.github_repository
