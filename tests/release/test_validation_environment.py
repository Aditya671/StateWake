"""Regression tests for locked validation-environment verification."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
from unittest.mock import patch

from scripts.release import verify_validation_environment as validation_environment


def _write_project(
    root: Path, *, dev: list[str], integrations: list[str], lock: str
) -> None:
    """Write the minimal project metadata needed by the environment verifier."""
    dev_lines = ", ".join(f'"{item}"' for item in dev)
    integration_lines = ", ".join(f'"{item}"' for item in integrations)
    (root / "pyproject.toml").write_text(
        f"""
[project]
name = "example"
version = "1.0.0"
[project.optional-dependencies]
integrations = [{integration_lines}]
[dependency-groups]
dev = [{dev_lines}]
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (root / "uv.lock").write_text(lock.strip() + "\n", encoding="utf-8")


def test_required_validation_distributions_are_derived_from_pyproject(
    tmp_path: Path,
) -> None:
    """The validation dependency contract follows project metadata rather than a static list."""
    _write_project(
        tmp_path,
        dev=["mypy==1", "pytest>=8"],
        integrations=["framework-one>=1", "framework_two[feature]>=2"],
        lock="""
version = 1
[[package]]
name = "framework-one"
version = "1.0.0"
[[package]]
name = "framework-two"
version = "2.0.0"
[[package]]
name = "mypy"
version = "1.0.0"
[[package]]
name = "pytest"
version = "8.0.0"
""",
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
    """Missing validation dependencies remain visible without triggering installation."""
    _write_project(
        tmp_path,
        dev=["also-not-installed-statewake-tool>=1"],
        integrations=["definitely-not-installed-statewake-sdk>=1"],
        lock="""
version = 1
[[package]]
name = "also-not-installed-statewake-tool"
version = "1.0.0"
[[package]]
name = "definitely-not-installed-statewake-sdk"
version = "1.0.0"
""",
    )
    with patch.object(
        importlib.metadata,
        "version",
        side_effect=importlib.metadata.PackageNotFoundError,
    ):
        result = validation_environment.validation_environment_status(tmp_path)
    assert result["status"] == "invalid_environment"
    assert result["missing_distributions"] == [
        "also-not-installed-statewake-tool",
        "definitely-not-installed-statewake-sdk",
    ]
    assert result["version_mismatches"] == {}


def test_environment_status_rejects_version_drift_from_lock(tmp_path: Path) -> None:
    """An installed tool with the wrong version is not accepted as the locked profile."""
    _write_project(
        tmp_path,
        dev=["pytest==9.1.1"],
        integrations=[],
        lock="""
version = 1
[[package]]
name = "pytest"
version = "9.1.1"
""",
    )
    with patch.object(importlib.metadata, "version", return_value="9.2.0"):
        result = validation_environment.validation_environment_status(tmp_path)
    assert result["status"] == "invalid_environment"
    assert result["version_mismatches"] == {
        "pytest": {"installed": "9.2.0", "locked": ["9.1.1"]}
    }
