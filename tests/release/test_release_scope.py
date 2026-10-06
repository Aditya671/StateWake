"""Current-project boundary regression tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from scripts.common.project_metadata import load_project_metadata
from scripts.common.project_paths import PROJECT_ROOT
from scripts.common.release_scope import (
    is_ignored_repository_path,
    is_release_input,
    release_input_files,
    repository_files,
)
from scripts.release import verify_release_candidate as candidate
from scripts.release.verify_supply_chain_provenance import source_tree_digest
from scripts.security.verify_continuous_security_assurance import snapshot


def test_release_scope_is_explicit() -> None:
    """Only maintained project inputs affect release identities."""
    metadata = load_project_metadata(PROJECT_ROOT)
    included = (
        metadata.package_init_relative.as_posix(),
        "scripts/common/project_paths.py",
        ".gitattributes",
        ".gitignore",
        "pyproject.toml",
        "uv.lock",
        "tests/test_release_identity.py",
        "scripts/release/verify_release_candidate.py",
        "ui/package.json",
        "ui/app/page.tsx",
        "data/README.md",
        "docs/governance/RELEASE_SCOPE.md",
        "docs/releases/README.md",
        metadata.current_release_notes_relative.as_posix(),
        f"docs/whitepaper/StateWake_Technical_White_Paper_v{metadata.version}.md",
        f"docs/whitepaper/StateWake_Technical_White_Paper_v{metadata.version}.pdf",
        ".github/workflows/python-publish.yml",
    )
    excluded = (
        "docs/verification/audit.md",
        "docs/releases/v0.3.0/RELEASE_NOTES.md",
        "docs/research/notes.md",
        "benchmarks/reports/generated.json",
        "scratch.py",
        "scratch/anything.py",
        "verification/output.json",
        "candidate-fingerprint.txt",
        "verification_manifest.txt",
        "ui/node_modules/next/index.js",
        "ui/.next/server/app.js",
        "ui/coverage/index.html",
        "ui/tsconfig.tsbuildinfo",
        ".venv/Lib/site-packages/openai/lib/.keep",
    )
    assert all(is_release_input(Path(name)) for name in included)
    assert all(not is_release_input(Path(name)) for name in excluded)


def test_current_whitepaper_matches_project_version_only() -> None:
    """The current white-paper boundary contains only the configured project version."""
    metadata = load_project_metadata(PROJECT_ROOT)
    whitepaper = PROJECT_ROOT / "docs/whitepaper"
    expected = {
        f"StateWake_Technical_White_Paper_v{metadata.version}.md",
        f"StateWake_Technical_White_Paper_v{metadata.version}.pdf",
    }
    actual = {
        path.name
        for path in whitepaper.glob("StateWake_Technical_White_Paper_v*.*")
        if path.suffix in {".md", ".pdf"}
    }
    assert actual == expected
    assert not (whitepaper / "Technical_Grounding_and_Source_Map.md").exists()


def test_local_dependency_trees_are_pruned_before_repository_enumeration(
    tmp_path: Path,
) -> None:
    """Local environments must not participate in repository structure or identity."""
    source = tmp_path / "src/statewake/example.py"
    source.parent.mkdir(parents=True)
    source.write_text("maintained", encoding="utf-8")
    venv_placeholder = tmp_path / ".venv/Lib/site-packages/openai/lib/.keep"
    venv_placeholder.parent.mkdir(parents=True)
    venv_placeholder.write_text("", encoding="utf-8")
    node_file = tmp_path / "ui/node_modules/next/index.js"
    node_file.parent.mkdir(parents=True)
    node_file.write_text("generated", encoding="utf-8")

    assert is_ignored_repository_path(venv_placeholder.relative_to(tmp_path))
    assert is_ignored_repository_path(node_file.relative_to(tmp_path))
    assert repository_files(tmp_path) == (source,)
    assert release_input_files(tmp_path) == (source,)


def test_git_text_checkout_policy_is_line_ending_stable() -> None:
    """Release-input text hashes must not depend on the checkout platform."""
    attributes = Path(__file__).resolve().parents[2] / ".gitattributes"
    assert "* text=auto eol=lf" in attributes.read_text(encoding="utf-8")


def test_release_input_order_is_platform_independent(tmp_path: Path) -> None:
    """Use POSIX path ordering rather than OS-specific Path comparisons."""
    package = tmp_path / "src/statewake"
    package.mkdir(parents=True)
    uppercase = package / "Z.py"
    lowercase = package / "a.py"
    uppercase.write_text("upper", encoding="utf-8")
    lowercase.write_text("lower", encoding="utf-8")

    assert release_input_files(tmp_path) == (uppercase, lowercase)


def test_all_release_digest_consumers_share_one_scope(tmp_path: Path) -> None:
    """One selector drives provenance, release candidate and security snapshots."""
    file = tmp_path / "src/statewake/example.py"
    file.parent.mkdir(parents=True)
    file.write_text("one", encoding="utf-8")
    with patch.object(candidate, "ROOT", tmp_path):
        first = candidate.tree_digest()
        assert first == source_tree_digest(tmp_path)
        assert tuple(release_input_files(tmp_path)) == (file,)
        assert tuple(snapshot(tmp_path)) == ("src/statewake/example.py",)
        noise = tmp_path / "docs/verification/review.md"
        noise.parent.mkdir(parents=True)
        noise.write_text("two", encoding="utf-8")
        assert candidate.tree_digest() == first
        file.write_text("three", encoding="utf-8")
        assert candidate.tree_digest() != first
