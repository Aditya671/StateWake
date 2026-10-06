"""Regression tests for Tier 8 supply-chain and release assurance."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from scripts.common.project_paths import PROJECT_ROOT
from scripts.common.release_identity import refresh_release_identity
from scripts.release.verify_supply_chain_provenance import (
    SupplyChainProvenanceError,
    project_metadata,
    source_tree_digest,
    validate_provenance_record,
    validate_verification_manifest,
)

ROOT = PROJECT_ROOT


@pytest.fixture(scope="module")
def candidate_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create one isolated candidate with freshly generated identity artifacts."""
    root = tmp_path_factory.mktemp("release-candidate") / "project"
    shutil.copytree(
        ROOT,
        root,
        ignore=shutil.ignore_patterns(
            ".git",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".venv",
            "__pycache__",
            "build",
            "dist",
            "verification",
            "node_modules",
            ".next",
        ),
    )
    refresh_release_identity(root)
    return root


def _record(root: Path, tmp_path: Path) -> tuple[dict[str, object], Path]:
    """Build one valid Tier 8 development provenance record around a test artifact."""
    artifact = tmp_path / "statewake-development-artifact.bin"
    artifact.write_bytes(b"statewake-tier8-test-artifact")
    metadata = project_metadata(root)
    source_digest = source_tree_digest(root)
    artifact_digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    record: dict[str, object] = {
        "schema_version": "1",
        "status": "verified",
        "release_status": "development-only",
        "distribution": metadata["distribution"],
        "version": metadata["version"],
        "source_revision": f"tree:{source_digest}",
        "source_tree_sha256": source_digest,
        "dependency_lock_sha256": metadata["dependency_lock_sha256"],
        "build_context": {
            "python": "3.13",
            "build_backend": "uv_build",
            "platform": "test-platform",
        },
        "build_steps": ["compileall", "test", "artifact-hash"],
        "security_tests": [
            {
                "name": "tier8-regression",
                "source_tree_sha256": source_digest,
                "dependency_lock_sha256": metadata["dependency_lock_sha256"],
                "status": "passed",
            }
        ],
        "artifact": {
            "name": artifact.name,
            "sha256": artifact_digest,
            "size_bytes": artifact.stat().st_size,
        },
        "verification": {
            "status": "verified",
            "artifact_sha256": artifact_digest,
            "source_tree_sha256": source_digest,
            "dependency_lock_sha256": metadata["dependency_lock_sha256"],
            "publication_authorized": False,
        },
    }
    return record, artifact


def test_supply_chain_metadata_is_derived_from_current_project(
    candidate_root: Path,
) -> None:
    """Project metadata must be internally consistent without frozen dependency prose."""
    metadata = project_metadata(candidate_root)
    assert metadata["distribution"] == "statewake-ai"
    assert isinstance(metadata["version"], str) and metadata["version"]
    assert metadata["lock_packages"] >= 1
    assert isinstance(metadata["dependencies"], list)
    assert isinstance(metadata["optional_dependencies"], dict)


def test_valid_provenance_binds_source_dependencies_and_artifact(
    candidate_root: Path, tmp_path: Path
) -> None:
    """Verify a complete provenance record validates against the exact artifact."""
    record, artifact = _record(candidate_root, tmp_path)
    validate_provenance_record(record, root=candidate_root, artifact_path=artifact)


def test_artifact_substitution_is_rejected(
    candidate_root: Path, tmp_path: Path
) -> None:
    """Verify changing the artifact after verification fails closed."""
    record, artifact = _record(candidate_root, tmp_path)
    artifact.write_bytes(b"attacker-substituted-artifact")
    with pytest.raises(
        SupplyChainProvenanceError, match="artifact (digest|size) mismatch"
    ):
        validate_provenance_record(record, root=candidate_root, artifact_path=artifact)


def test_source_drift_is_rejected(candidate_root: Path, tmp_path: Path) -> None:
    """Verify provenance cannot be reused after an input-source change."""
    record, artifact = _record(candidate_root, tmp_path)
    original = candidate_root / "README.md"
    original_bytes = original.read_bytes()
    try:
        original.write_bytes(original_bytes + b"\n# temporary test drift\n")
        with pytest.raises(
            SupplyChainProvenanceError,
            match="(source tree digest|verification manifest|candidate fingerprint)",
        ):
            validate_provenance_record(
                record, root=candidate_root, artifact_path=artifact
            )
    finally:
        original.write_bytes(original_bytes)


def test_security_test_provenance_must_match_source_and_lock(
    candidate_root: Path, tmp_path: Path
) -> None:
    """Verify security evidence is bound to the exact source and dependency state."""
    record, artifact = _record(candidate_root, tmp_path)
    tests = record["security_tests"]
    assert isinstance(tests, list)
    tests[0]["dependency_lock_sha256"] = "0" * 64  # type: ignore[index]
    with pytest.raises(
        SupplyChainProvenanceError, match="security test dependency mismatch"
    ):
        validate_provenance_record(record, root=candidate_root, artifact_path=artifact)


def test_development_record_cannot_authorize_publication(
    candidate_root: Path, tmp_path: Path
) -> None:
    """Verify development evidence never becomes a publication authorization."""
    record, artifact = _record(candidate_root, tmp_path)
    verification = record["verification"]
    assert isinstance(verification, dict)
    verification["publication_authorized"] = True
    with pytest.raises(SupplyChainProvenanceError, match="authorize publication"):
        validate_provenance_record(record, root=candidate_root, artifact_path=artifact)


def test_freshly_generated_manifest_matches_candidate(candidate_root: Path) -> None:
    """A generated release identity verifies without depending on checked-in freshness."""
    refresh_release_identity(candidate_root)
    validate_verification_manifest(candidate_root)


def test_verification_manifest_detects_source_hash_drift(tmp_path: Path) -> None:
    """Reject a manifest when source bytes change after identity generation."""
    root = tmp_path / "candidate"
    target = root / "src" / "statewake" / "example.py"
    target.parent.mkdir(parents=True)
    target.write_text("value = 1\n", encoding="utf-8")
    refresh_release_identity(root)
    target.write_text("value = 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="verification manifest"):
        validate_verification_manifest(root)


def test_release_input_scope_ignores_ancillary_files(tmp_path: Path) -> None:
    """Historical, scratch and generated files cannot change release identity."""
    source = tmp_path / "src" / "statewake" / "core.py"
    source.parent.mkdir(parents=True)
    source.write_text("value = 1\n", encoding="utf-8")
    first = source_tree_digest(tmp_path)
    for relative in (
        "docs/verification/audit.md",
        "docs/releases/v0.2.0/history.md",
        "docs/research/notes.md",
        "scratch/temporary.py",
        "verification/generated.json",
        "benchmarks/reports/output.json",
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("unrelated", encoding="utf-8")
        assert source_tree_digest(tmp_path) == first, relative
    source.write_text("value = 2\n", encoding="utf-8")
    assert source_tree_digest(tmp_path) != first


def test_current_verification_code_changes_release_identity(tmp_path: Path) -> None:
    """Maintained release gates are inputs even though they do not ship in the wheel."""
    gate = tmp_path / "scripts" / "release" / "verify.py"
    gate.parent.mkdir(parents=True)
    gate.write_text("before", encoding="utf-8")
    before = source_tree_digest(tmp_path)
    gate.write_text("after", encoding="utf-8")
    assert source_tree_digest(tmp_path) != before
