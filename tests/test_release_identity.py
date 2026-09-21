"""Regression checks for the public StateWake package identity and documentation boundary."""

import statewake
from config.project_paths import PROJECT_ROOT

ROOT = PROJECT_ROOT


def test_public_identity_is_statewake() -> None:
    """Verify the supported StateWake distribution, import namespace, and CLI identity."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "statewake-ai"' in pyproject
    assert 'statewake = "statewake.cli.main:main"' in pyproject
    assert statewake.__version__ == "0.4.0"


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


def test_removed_identity_is_absent_from_active_project() -> None:
    """Prevent accidental reintroduction of the pre-StateWake active package identity."""
    forbidden = (
        "Agent " + "Reliability Engine",
        "agent-" + "reliability-engine",
        "agent_" + "reliability_engine",
        "agent" + "ctl",
    )
    roots = (
        ROOT / "src",
        ROOT / "tests",
        ROOT / "scripts",
        ROOT / "docs",
        ROOT / "README.md",
        ROOT / "pyproject.toml",
    )
    files = [path for root in roots if root.is_file() for path in [root]]
    files.extend(path for root in roots if root.is_dir() for path in root.rglob("*"))
    for path in files:
        if not path.is_file() or path.suffix not in {
            ".py",
            ".md",
            ".toml",
            ".yml",
            ".yaml",
        }:
            continue
        text = path.read_text(encoding="utf-8")
        assert not any(token in text for token in forbidden), path
