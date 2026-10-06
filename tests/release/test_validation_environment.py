"""Regression tests for the canonical SDLC validation dependency profile."""

from __future__ import annotations

import importlib.metadata
import re
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


def test_ci_uses_one_os_python_quality_matrix() -> None:
    """Linux and Windows quality checks must share one authoritative job definition."""
    workflow = (validation_environment.ROOT / ".github/workflows/ci.yml").read_text(
        encoding="utf-8"
    )
    assert re.search(r"^  quality-and-tests:", workflow, re.MULTILINE)
    assert "windows-quality-and-tests:" not in workflow
    assert "fail-fast: false" in workflow
    assert "os: [ubuntu-latest, windows-latest]" in workflow
    assert 'python-version: ["3.11", "3.12", "3.13"]' in workflow
    assert "if: matrix.os == 'windows-latest'" in workflow


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


def test_publication_basis_workflow_uses_create_script_cli_contract() -> None:
    """Publication-basis workflow flags must match the script argparse contract."""
    workflow = (
        validation_environment.ROOT / ".github/workflows/python-publish.yml"
    ).read_text(encoding="utf-8")
    assert "scripts/release/create_publication_basis.py" in workflow
    assert '--source-revision "$GITHUB_SHA"' in workflow
    create_invocation = workflow.split(
        "scripts/release/create_publication_basis.py", 1
    )[1].split("Generate build provenance", 1)[0]
    assert "--expected-source-revision" not in create_invocation


def test_publication_basis_script_keeps_backwards_compatible_revision_alias() -> None:
    """Older callers should fail less often while workflows use the canonical flag."""
    script = (
        validation_environment.ROOT / "scripts/release/create_publication_basis.py"
    ).read_text(encoding="utf-8")
    assert '"--source-revision"' in script
    assert '"--expected-source-revision"' in script
    assert 'dest="source_revision"' in script


def _script_declared_flags(relative_script: str) -> set[str]:
    script = (validation_environment.ROOT / relative_script).read_text(encoding="utf-8")
    flags: set[str] = set()
    for double_quoted, single_quoted in re.findall(
        r'"(--[a-z0-9-]+)"|\'(--[a-z0-9-]+)\'', script
    ):
        flags.add(double_quoted or single_quoted)
    return flags


def _workflow_script_invocations(workflow: str) -> list[tuple[str, set[str]]]:
    lines = workflow.splitlines()
    invocations: list[tuple[str, set[str]]] = []
    script_pattern = re.compile(r"scripts/[A-Za-z0-9_./-]+\.py")
    flag_pattern = re.compile(r"(?<![\w-])(--[a-z0-9-]+)")
    for index, line in enumerate(lines):
        match = script_pattern.search(line)
        if not match:
            continue
        script = match.group(0)
        flags = set(flag_pattern.findall(line[match.end() :]))
        cursor = index + 1
        while cursor < len(lines):
            stripped = lines[cursor].strip()
            if not stripped or not stripped.startswith("--"):
                break
            flags.update(flag_pattern.findall(stripped))
            cursor += 1
        invocations.append((script, flags))
    return invocations


def test_workflow_project_script_flags_match_declared_argparse_contracts() -> None:
    """Workflow-maintained script calls must not drift from script CLI flags."""
    checked: list[str] = []
    for workflow_path in sorted(
        (validation_environment.ROOT / ".github/workflows").glob("*.yml")
    ):
        workflow = workflow_path.read_text(encoding="utf-8")
        for script, used_flags in _workflow_script_invocations(workflow):
            declared = _script_declared_flags(script)
            unknown = sorted(used_flags - declared)
            message = f"{workflow_path.name}: {script} uses unknown flags {unknown}"
            assert not unknown, message
            checked.append(f"{workflow_path.name}:{script}")
    assert checked
