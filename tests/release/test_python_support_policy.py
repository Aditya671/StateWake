"""Regression tests for the declared Python support boundary."""

from __future__ import annotations

import tomllib

from config.project_paths import PROJECT_ROOT

ROOT = PROJECT_ROOT
SUPPORTED = ("3.11", "3.12", "3.13")


def _pyproject() -> dict[str, object]:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        return tomllib.load(stream)


def test_v040_requires_python_stops_before_314() -> None:
    project = _pyproject()["project"]
    assert isinstance(project, dict)
    assert project["requires-python"] == ">=3.11,<3.14"


def test_v040_classifiers_advertise_only_qualified_minors() -> None:
    project = _pyproject()["project"]
    assert isinstance(project, dict)
    classifiers = project["classifiers"]
    assert isinstance(classifiers, list)
    for version in SUPPORTED:
        assert f"Programming Language :: Python :: {version}" in classifiers
    assert "Programming Language :: Python :: 3.14" not in classifiers


def test_ci_and_release_matrices_do_not_claim_python_314() -> None:
    workflow_paths = (
        ROOT / ".github/workflows/ci.yml",
        ROOT / ".github/workflows/release-verification.yml",
        ROOT / ".github/workflows/python-publish.yml",
    )
    for path in workflow_paths:
        text = path.read_text(encoding="utf-8")
        for version in SUPPORTED:
            assert version in text
        assert "3.14" not in text


def test_current_docs_state_314_is_unsupported_for_v040() -> None:
    policy = (ROOT / "docs/user-guide/python-support.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    governance = (ROOT / "docs/governance/RELEASE_GOVERNANCE.md").read_text(
        encoding="utf-8"
    )
    assert ">=3.11,<3.14" in policy
    assert "Python 3.14 is intentionally" in policy
    assert "forced wheel installation" in policy
    assert "Python 3.14 is intentionally outside" in readme
    assert "Python 3.14 is deliberately outside" in governance


def test_fastapi_trial_boundary_is_documented_without_support_claim() -> None:
    policy = (ROOT / "docs/user-guide/python-support.md").read_text(encoding="utf-8")
    assert "FastAPI Full Stack Template" in policy
    assert "outside the StateWake v0.4.0 compatibility matrix" in policy
    assert "not a StateWake compatibility result" in policy
