"""Regression tests for Tier 8 supply-chain and release assurance."""

from __future__ import annotations

from pathlib import Path

import pytest

from config.project_paths import PROJECT_ROOT
from scripts.release.verify_supply_chain_provenance import (
    SupplyChainProvenanceError,
    project_metadata,
    source_tree_digest,
    validate_provenance_record,
    validate_verification_manifest,
)

ROOT = PROJECT_ROOT


def _record(tmp_path: Path) -> tuple[dict[str, object], Path]:
    """Build one valid Tier 8 development provenance record around a test artifact."""
    artifact = tmp_path / "statewake-development-artifact.bin"
    artifact.write_bytes(b"statewake-tier8-test-artifact")
    metadata = project_metadata(ROOT)
    source_digest = source_tree_digest(ROOT)
    artifact_digest = __import__("hashlib").sha256(artifact.read_bytes()).hexdigest()
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


def test_supply_chain_contract_matches_existing_release_plumbing() -> None:
    """Verify the Tier 8 contract reuses the existing release verification workflow."""
    metadata = project_metadata(ROOT)
    assert metadata["distribution"] == "statewake-ai"
    assert metadata["version"] == "0.4.0"
    assert metadata["lock_packages"] >= 1
    assert metadata["optional_dependencies"] == {}

    dependencies = set(metadata["dependencies"])
    expected_runtime_dependencies = {
        "pynacl==1.6.2",
        "opentelemetry-api==1.44.0",
        "filelock==3.32.4",
        "duckdb==1.5.5",
        "openpyxl==3.1.5",
        "pyarrow==25.0.1",
        "sqlalchemy==2.0.54",
        "opentelemetry-sdk>=1.44,<2",
        "openai-agents>=0.3,<1",
        "langchain-core>=0.3,<2",
        "langgraph>=0.3,<2",
        "llama-index-core>=0.12,<1",
    }
    assert expected_runtime_dependencies <= dependencies


def test_valid_provenance_binds_source_dependencies_and_artifact(
    tmp_path: Path,
) -> None:
    """Verify a complete provenance record validates against the exact artifact."""
    record, artifact = _record(tmp_path)
    validate_provenance_record(record, root=ROOT, artifact_path=artifact)


def test_artifact_substitution_is_rejected(tmp_path: Path) -> None:
    """Verify changing the artifact after verification fails closed."""
    record, artifact = _record(tmp_path)
    artifact.write_bytes(b"attacker-substituted-artifact")
    with pytest.raises(
        SupplyChainProvenanceError, match="artifact (digest|size) mismatch"
    ):
        validate_provenance_record(record, root=ROOT, artifact_path=artifact)


def test_source_drift_is_rejected(tmp_path: Path) -> None:
    """Verify provenance cannot be reused after an input-source change."""
    record, artifact = _record(tmp_path)
    original = ROOT / "docs" / "security" / "supply_chain_release_assurance.md"
    original_bytes = original.read_bytes()
    try:
        original.write_bytes(original_bytes + b"\n# temporary test drift\n")
        with pytest.raises(
            SupplyChainProvenanceError,
            match="(source tree digest|verification manifest)",
        ):
            validate_provenance_record(record, root=ROOT, artifact_path=artifact)
    finally:
        original.write_bytes(original_bytes)


def test_security_test_provenance_must_match_source_and_lock(tmp_path: Path) -> None:
    """Verify security evidence is bound to the exact source and dependency state."""
    record, artifact = _record(tmp_path)
    tests = record["security_tests"]
    assert isinstance(tests, list)
    tests[0]["dependency_lock_sha256"] = "0" * 64  # type: ignore[index]
    with pytest.raises(
        SupplyChainProvenanceError, match="security test dependency mismatch"
    ):
        validate_provenance_record(record, root=ROOT, artifact_path=artifact)


def test_development_record_cannot_authorize_publication(tmp_path: Path) -> None:
    """Verify Tier 8 development evidence never becomes a publication authorization."""
    record, artifact = _record(tmp_path)
    verification = record["verification"]
    assert isinstance(verification, dict)
    verification["publication_authorized"] = True
    with pytest.raises(SupplyChainProvenanceError, match="authorize publication"):
        validate_provenance_record(record, root=ROOT, artifact_path=artifact)


def test_verification_manifest_matches_current_source_tree() -> None:
    """Verify the candidate manifest describes every immutable source-tree file exactly."""
    validate_verification_manifest(ROOT)


def test_verification_manifest_detects_source_hash_drift(tmp_path: Path) -> None:
    """Reject a manifest when a recorded source digest is changed."""
    import shutil

    root = tmp_path / "candidate"
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
        ),
    )
    target = root / "README.md"
    target.write_text(target.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(SupplyChainProvenanceError, match="verification manifest"):
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
