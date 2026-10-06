"""Regression checks for the public StateWake package identity and documentation boundary."""

from __future__ import annotations

import ast
import tomllib

import statewake
from scripts.common.project_paths import PROJECT_ROOT

ROOT = PROJECT_ROOT


def _package_constants() -> dict[str, str]:
    tree = ast.parse(
        (ROOT / "src/statewake/__init__.py").read_text(encoding="utf-8"),
        filename="src/statewake/__init__.py",
    )
    values: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                values[target.id] = node.value.value
    return values


def test_public_identity_matches_structured_project_metadata() -> None:
    """Verify distribution/import/CLI identity through maintained metadata authorities."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))[
        "project"
    ]
    scripts = project.get("scripts", {})
    constants = _package_constants()

    assert project["name"] == "statewake-ai"
    assert scripts.get("statewake") == "statewake.cli.main:main"
    assert constants.get("__version__") == project["version"]
    assert statewake.__version__ == project["version"]


def test_release_docs_exist() -> None:
    """Verify the portable release-documentation set is present."""
    required = {
        "index.md",
        "what-is-statewake.md",
        "getting-started.md",
        "python-integration.md",
        "http-api.md",
        "evidence-lifecycle.md",
        "architecture.md",
        "security.md",
        "cli.md",
        "concepts.md",
        "integration-patterns.md",
        "data-and-proof.md",
        "troubleshooting.md",
        "faq.md",
        "release.md",
    }
    actual = {path.name for path in (ROOT / "docs" / "user-guide").glob("*.md")}
    assert required <= actual
