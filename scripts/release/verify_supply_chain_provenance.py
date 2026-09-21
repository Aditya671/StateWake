"""Verify the StateWake Tier 8 supply-chain provenance contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

from config.project_paths import PROJECT_ROOT

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))


ROOT = PROJECT_ROOT


def _project_version() -> str:
    """Read the authoritative package version from pyproject.toml."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return str(project["project"]["version"])


EXPECTED_VERSION = _project_version()
EXPECTED_DISTRIBUTION = "statewake-ai"
REQUIRED_WORKFLOW_MARKERS = (
    "uv lock --check",
    "uv build",
    "sha256sum dist/*",
    "pip-audit",
    "cyclonedx",
    "actions/attest-build-provenance",
)
EXCLUDED_TREE_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "build",
    "verification",
}
EXCLUDED_TREE_FILES = {
    "candidate-fingerprint.txt",
    "verification_manifest.txt",
    "test_results.txt",
    "pytest_fresh.txt",
}


class SupplyChainProvenanceError(ValueError):
    """Raised when Tier 8 provenance evidence is inconsistent or incomplete."""


def sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hexadecimal digest for bytes."""
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of one file."""
    return sha256_bytes(path.read_bytes())


def source_tree_digest(root: Path = ROOT) -> str:
    """Return a deterministic digest over immutable source/build-input files."""
    digest = hashlib.sha256()
    paths = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and not any(part in EXCLUDED_TREE_PARTS for part in path.parts)
        and path.name not in EXCLUDED_TREE_FILES
        and path.name not in EXCLUDED_TREE_FILES
    )
    for path in paths:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def verification_manifest(root: Path = ROOT) -> dict[str, str]:
    """Read the exact source-tree verification manifest."""
    manifest_path = root / "verification_manifest.txt"
    if not manifest_path.is_file():
        raise SupplyChainProvenanceError("verification manifest is missing")
    records: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        manifest_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        parts = raw_line.split("  ", 1)
        if len(parts) != 2:
            raise SupplyChainProvenanceError(
                f"invalid verification manifest record at line {line_number}"
            )
        digest, relative = parts
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise SupplyChainProvenanceError(
                f"invalid verification manifest digest at line {line_number}"
            )
        if not relative or Path(relative).is_absolute():
            raise SupplyChainProvenanceError(
                f"invalid verification manifest path at line {line_number}"
            )
        if relative in records:
            raise SupplyChainProvenanceError(
                f"duplicate verification manifest path: {relative}"
            )
        records[relative] = digest
    return records


def validate_verification_manifest(root: Path = ROOT) -> None:
    """Verify manifest membership and content digests against the current tree."""
    recorded = verification_manifest(root)
    actual = {
        path.relative_to(root).as_posix(): file_sha256(path)
        for path in root.rglob("*")
        if path.is_file()
        and not any(
            part in EXCLUDED_TREE_PARTS for part in path.relative_to(root).parts
        )
        and path.name not in EXCLUDED_TREE_FILES
    }
    if recorded != actual:
        missing = sorted(set(actual) - set(recorded))
        unexpected = sorted(set(recorded) - set(actual))
        mismatched = sorted(
            path
            for path in set(actual) & set(recorded)
            if actual[path] != recorded[path]
        )
        details: list[str] = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if unexpected:
            details.append("unexpected=" + ",".join(unexpected))
        if mismatched:
            details.append("mismatched=" + ",".join(mismatched))
        raise SupplyChainProvenanceError(
            "verification manifest does not match source tree: " + "; ".join(details)
        )


def project_metadata(root: Path = ROOT) -> dict[str, Any]:
    """Read and validate the declared package identity and locked dependencies."""
    pyproject_path = root / "pyproject.toml"
    lock_path = root / "uv.lock"
    package_path = root / "src" / "statewake" / "__init__.py"
    workflow_path = root / ".github" / "workflows" / "release-verification.yml"
    project = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    package_text = package_path.read_text(encoding="utf-8")
    workflow = workflow_path.read_text(encoding="utf-8")

    project_name = project["project"]["name"]
    version = project["project"]["version"]
    dependencies = tuple(sorted(project["project"].get("dependencies", ())))
    optional_dependencies = {
        str(extra): tuple(sorted(values))
        for extra, values in project["project"].get("optional-dependencies", {}).items()
    }
    lock_project = next(
        (item for item in lock["package"] if item["name"] == EXPECTED_DISTRIBUTION),
        None,
    )
    if lock_project is None:
        raise SupplyChainProvenanceError(
            "uv.lock is missing the statewake-ai project entry"
        )
    if project_name != EXPECTED_DISTRIBUTION or version != EXPECTED_VERSION:
        raise SupplyChainProvenanceError(
            "project identity/version drifted from the current package version"
        )
    if f'__version__ = "{EXPECTED_VERSION}"' not in package_text:
        raise SupplyChainProvenanceError(
            "package __version__ drifted from the current package version"
        )
    missing_markers = [
        marker for marker in REQUIRED_WORKFLOW_MARKERS if marker not in workflow
    ]
    if missing_markers:
        raise SupplyChainProvenanceError(
            "release-verification workflow is missing Tier 8 markers: "
            + ", ".join(missing_markers)
        )

    locked_names = {
        item["name"]: item["version"]
        for item in lock["package"]
        if item.get("version") is not None
    }
    for dependency in dependencies:
        name = dependency.split("==", 1)[0].split("[", 1)[0]
        if name not in locked_names:
            raise SupplyChainProvenanceError(
                f"dependency {name!r} is not represented in uv.lock"
            )
    for extra, extra_dependencies in optional_dependencies.items():
        for dependency in extra_dependencies:
            name = dependency.split("==", 1)[0].split("[", 1)[0]
            if name not in locked_names:
                raise SupplyChainProvenanceError(
                    f"optional dependency {name!r} for extra {extra!r} is not represented in uv.lock"
                )

    return {
        "distribution": project_name,
        "version": version,
        "dependencies": list(dependencies),
        "optional_dependencies": {
            key: list(value) for key, value in optional_dependencies.items()
        },
        "lock_packages": len(lock["package"]),
        "dependency_lock_sha256": file_sha256(lock_path),
    }


def validate_provenance_record(
    record: dict[str, Any],
    *,
    root: Path = ROOT,
    artifact_path: Path | None = None,
) -> None:
    """Validate the complete source-to-artifact Tier 8 provenance contract."""
    required = {
        "schema_version",
        "status",
        "release_status",
        "distribution",
        "version",
        "source_revision",
        "source_tree_sha256",
        "dependency_lock_sha256",
        "build_context",
        "build_steps",
        "security_tests",
        "artifact",
        "verification",
    }
    missing = required - record.keys()
    if missing:
        raise SupplyChainProvenanceError(
            "provenance record missing: " + ", ".join(sorted(missing))
        )
    metadata = project_metadata(root)
    validate_verification_manifest(root)
    if record["schema_version"] != "1":
        raise SupplyChainProvenanceError("unsupported provenance schema")
    if record["status"] != "verified":
        raise SupplyChainProvenanceError("provenance record is not verified")
    if record["release_status"] != "development-only":
        raise SupplyChainProvenanceError("Tier 8 record must remain development-only")
    if record["distribution"] != metadata["distribution"]:
        raise SupplyChainProvenanceError("distribution identity mismatch")
    if record["version"] != metadata["version"]:
        raise SupplyChainProvenanceError("version identity mismatch")
    if not re.fullmatch(r"[0-9a-f]{64}", record["source_tree_sha256"]):
        raise SupplyChainProvenanceError("invalid source_tree_sha256")
    actual_source_digest = source_tree_digest(root)
    if record["source_tree_sha256"] != actual_source_digest:
        raise SupplyChainProvenanceError("source tree digest does not match evidence")
    fingerprint_path = root / "candidate-fingerprint.txt"
    if fingerprint_path.is_file():
        fingerprint = fingerprint_path.read_text(encoding="utf-8").strip()
        if fingerprint != actual_source_digest:
            raise SupplyChainProvenanceError(
                "candidate fingerprint does not match source tree"
            )
    if record["dependency_lock_sha256"] != metadata["dependency_lock_sha256"]:
        raise SupplyChainProvenanceError(
            "dependency lock digest does not match uv.lock"
        )
    if not record["source_revision"]:
        raise SupplyChainProvenanceError("source_revision must be explicit")

    build_context = record["build_context"]
    for field in ("python", "build_backend", "platform"):
        if not isinstance(build_context.get(field), str) or not build_context[field]:
            raise SupplyChainProvenanceError(f"build_context.{field} must be explicit")
    if not isinstance(record["build_steps"], list) or not record["build_steps"]:
        raise SupplyChainProvenanceError("build_steps must be a non-empty list")

    tests = record["security_tests"]
    if not isinstance(tests, list) or not tests:
        raise SupplyChainProvenanceError("security_tests must be a non-empty list")
    for test in tests:
        for field in ("name", "source_tree_sha256", "dependency_lock_sha256", "status"):
            if field not in test:
                raise SupplyChainProvenanceError(f"security test missing {field}")
        if test["status"] != "passed":
            raise SupplyChainProvenanceError(
                f"security test is not passed: {test['name']}"
            )
        if test["source_tree_sha256"] != record["source_tree_sha256"]:
            raise SupplyChainProvenanceError(
                f"security test source mismatch: {test['name']}"
            )
        if test["dependency_lock_sha256"] != record["dependency_lock_sha256"]:
            raise SupplyChainProvenanceError(
                f"security test dependency mismatch: {test['name']}"
            )

    artifact = record["artifact"]
    for field in ("name", "sha256", "size_bytes"):
        if field not in artifact:
            raise SupplyChainProvenanceError(f"artifact missing {field}")
    if not re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"]):
        raise SupplyChainProvenanceError("invalid artifact sha256")
    if not isinstance(artifact["size_bytes"], int) or artifact["size_bytes"] <= 0:
        raise SupplyChainProvenanceError("invalid artifact size")
    if artifact_path is not None:
        if not artifact_path.is_file():
            raise SupplyChainProvenanceError(
                f"artifact does not exist: {artifact_path}"
            )
        if artifact_path.name != artifact["name"]:
            raise SupplyChainProvenanceError("artifact name mismatch")
        if artifact_path.stat().st_size != artifact["size_bytes"]:
            raise SupplyChainProvenanceError("artifact size mismatch")
        if file_sha256(artifact_path) != artifact["sha256"]:
            raise SupplyChainProvenanceError("artifact digest mismatch")

    verification = record["verification"]
    if verification.get("status") != "verified":
        raise SupplyChainProvenanceError("verification status is not verified")
    if verification.get("artifact_sha256") != artifact["sha256"]:
        raise SupplyChainProvenanceError("verification is not bound to exact artifact")
    if verification.get("source_tree_sha256") != record["source_tree_sha256"]:
        raise SupplyChainProvenanceError("verification source binding mismatch")
    if verification.get("dependency_lock_sha256") != record["dependency_lock_sha256"]:
        raise SupplyChainProvenanceError("verification dependency binding mismatch")
    if verification.get("publication_authorized") is not False:
        raise SupplyChainProvenanceError(
            "Tier 8 development record must not authorize publication"
        )


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provenance", type=Path, help="JSON provenance record")
    parser.add_argument(
        "--artifact", type=Path, default=None, help="Exact artifact to verify"
    )
    return parser.parse_args()


def main() -> int:
    """Verify one Tier 8 provenance record."""
    args = _parse_args()
    record = json.loads(args.provenance.read_text(encoding="utf-8"))
    validate_provenance_record(record, root=ROOT, artifact_path=args.artifact)
    print("tier8-supply-chain: VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
