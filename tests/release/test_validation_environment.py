"""Regression tests for the canonical SDLC validation dependency profile."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
from unittest.mock import patch

from scripts.release import verify_validation_environment as validation_environment


def test_required_validation_distributions_are_derived_from_pyproject(
    tmp_path: Path,
) -> None:
    """The validation dependency contract follows project metadata rather than a static list."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "example"
version = "1.0.0"
[project.optional-dependencies]
integrations = ["framework-one>=1", "framework_two[feature]>=2"]
[dependency-groups]
dev = ["mypy==1", "pytest>=8"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    assert validation_environment.required_validation_distributions(tmp_path) == (
        "framework-one",
        "framework_two",
        "mypy",
        "pytest",
    )


def test_environment_status_fails_closed_for_missing_distribution(
    tmp_path: Path,
) -> None:
    """Missing validation dependencies must be visible before mypy or pytest begin."""
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "example"
version = "1.0.0"
[project.optional-dependencies]
integrations = ["definitely-not-installed-statewake-sdk>=1"]
[dependency-groups]
dev = ["also-not-installed-statewake-tool>=1"]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    with patch.object(
        importlib.metadata,
        "version",
        side_effect=importlib.metadata.PackageNotFoundError,
    ):
        result = validation_environment.validation_environment_status(tmp_path)
    assert result["status"] == "missing_dependencies"
    assert result["missing_distributions"] == [
        "also-not-installed-statewake-tool",
        "definitely-not-installed-statewake-sdk",
    ]


def test_publication_workflow_installs_full_validation_profile() -> None:
    """The publish workflow must match the dependency profile required by SDLC mypy/tests."""
    workflow = (
        validation_environment.ROOT / ".github/workflows/python-publish.yml"
    ).read_text(encoding="utf-8")
    assert "uv sync --locked --python 3.13 --group dev --extra integrations" in workflow


def test_sdlc_workflows_preserve_the_prepared_environment() -> None:
    """Workflow invocation must preserve extras and the explicitly synced Python."""
    expected = {
        ".github/workflows/ci.yml": (
            "uv run --no-sync --python ${{ matrix.python-version }} python "
            "scripts/release/run_sdlc_validation.py --profile check"
        ),
        ".github/workflows/python-publish.yml": (
            "uv run --no-sync --python 3.13 python "
            "scripts/release/run_sdlc_validation.py --profile release"
        ),
    }
    for relative, command in expected.items():
        workflow = (validation_environment.ROOT / relative).read_text(encoding="utf-8")
        assert command in workflow
