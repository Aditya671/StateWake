"""Current-project boundary regression tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from scripts.common.release_scope import is_release_input, release_input_files
from scripts.release import verify_release_candidate as candidate
from scripts.release.verify_supply_chain_provenance import source_tree_digest
from scripts.security.verify_continuous_security_assurance import snapshot


def test_release_scope_is_explicit() -> None:
    """Only maintained project inputs affect release identities."""
    included = (
        "src/statewake/__init__.py",
        "config/project_paths.py",
        ".gitattributes",
        "pyproject.toml",
        "uv.lock",
        "tests/test_release_identity.py",
        "scripts/release/verify_release_candidate.py",
        "docs/governance/RELEASE_SCOPE.md",
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
    )
    assert all(is_release_input(Path(name)) for name in included)
    assert all(not is_release_input(Path(name)) for name in excluded)


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
