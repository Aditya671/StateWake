"""Verify the StateWake Tier 8 supply-chain provenance contract."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from scripts.common import release_identity as _release_identity  # noqa: E402
from scripts.common.project_metadata import load_project_metadata  # noqa: E402
from scripts.common.project_paths import PROJECT_ROOT  # noqa: E402

ROOT = PROJECT_ROOT


ReleaseIdentityError = _release_identity.ReleaseIdentityError


class SupplyChainProvenanceError(ValueError):
    """Raised when Tier 8 provenance evidence is inconsistent or incomplete."""


def file_sha256(path: Path) -> str:
    """Return the SHA-256 digest of one file through the canonical identity helper."""
    return _release_identity.file_sha256(path)


def source_tree_digest(root: Path = ROOT) -> str:
    """Return the deterministic digest of selected release inputs."""
    return _release_identity.source_tree_digest(root)


def verification_manifest(root: Path = ROOT) -> dict[str, str]:
    """Read the persisted release-input verification manifest."""
    return _release_identity.read_manifest(root)


def validate_verification_manifest(root: Path = ROOT) -> None:
    """Validate the persisted manifest against current release inputs."""
    _release_identity.validate_verification_manifest(root)


def _package_constant(root: Path, name: str) -> str:
    """Read one literal package constant from ``statewake.__init__`` via AST."""
    metadata = load_project_metadata(root)
    path = root / metadata.package_init_relative
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
            continue
        if any(
            isinstance(target, ast.Name) and target.id == name for target in targets
        ):
            return value.value
    raise SupplyChainProvenanceError(f"package constant {name!r} is missing")


def _dependency_name(requirement: str) -> str:
    """Extract a normalized distribution name from one PEP 508-like requirement."""
    name = re.split(r"[<>=!~;\[ ]", requirement, maxsplit=1)[0].strip()
    if not name:
        raise SupplyChainProvenanceError(
            f"invalid dependency requirement: {requirement!r}"
        )
    return name.lower().replace("_", "-")


def project_metadata(root: Path = ROOT) -> dict[str, Any]:
    """Read and validate package identity and lock coverage structurally."""
    pyproject_path = root / "pyproject.toml"
    lock_path = root / "uv.lock"
    project_document = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    lock = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    project = project_document["project"]

    metadata = load_project_metadata(root)
    project_name = str(project["name"])
    version = str(project["version"])
    package_version = _package_constant(root, "__version__")
    dependencies = tuple(sorted(str(item) for item in project.get("dependencies", ())))
    optional_dependencies = {
        str(extra): tuple(sorted(str(item) for item in values))
        for extra, values in project.get("optional-dependencies", {}).items()
    }
    lock_project = next(
        (
            item
            for item in lock["package"]
            if str(item.get("name", "")).lower().replace("_", "-")
            == metadata.distribution.lower().replace("_", "-")
        ),
        None,
    )
    if lock_project is None:
        raise SupplyChainProvenanceError(
            f"uv.lock is missing the {metadata.distribution} project entry"
        )
    lock_version = str(lock_project.get("version", ""))
    if project_name != metadata.distribution:
        raise SupplyChainProvenanceError(
            f"project distribution does not match canonical metadata: {project_name!r}"
        )
    if version != package_version or version != lock_version:
        raise SupplyChainProvenanceError(
            "project, package, and lock versions are inconsistent"
        )

    locked_names = {
        str(item["name"]).lower().replace("_", "-")
        for item in lock["package"]
        if item.get("name") is not None
    }
    for dependency in dependencies:
        name = _dependency_name(dependency)
        if name not in locked_names:
            raise SupplyChainProvenanceError(
                f"dependency {name!r} is not represented in uv.lock"
            )
    for extra, extra_dependencies in optional_dependencies.items():
        for dependency in extra_dependencies:
            name = _dependency_name(dependency)
            if name not in locked_names:
                raise SupplyChainProvenanceError(
                    f"optional dependency {name!r} for extra {extra!r} "
                    "is not represented in uv.lock"
                )

    scripts = project.get("scripts", {})
    if (
        not isinstance(scripts, dict)
        or scripts.get(metadata.cli_name) != metadata.cli_target
    ):
        raise SupplyChainProvenanceError(
            f"{metadata.cli_name} CLI entry point is missing or invalid"
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
    try:
        _release_identity.validate_release_identity(root)
    except ReleaseIdentityError as exc:
        raise SupplyChainProvenanceError(str(exc)) from exc
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
    if (
        not isinstance(record["source_tree_sha256"], str)
        or re.fullmatch(r"[0-9a-f]{64}", record["source_tree_sha256"]) is None
    ):
        raise SupplyChainProvenanceError("invalid source_tree_sha256")
    actual_source_digest = source_tree_digest(root)
    if record["source_tree_sha256"] != actual_source_digest:
        raise SupplyChainProvenanceError("source tree digest does not match evidence")
    if record["dependency_lock_sha256"] != metadata["dependency_lock_sha256"]:
        raise SupplyChainProvenanceError(
            "dependency lock digest does not match uv.lock"
        )
    if not record["source_revision"]:
        raise SupplyChainProvenanceError("source_revision must be explicit")

    build_context = record["build_context"]
    if not isinstance(build_context, dict):
        raise SupplyChainProvenanceError("build_context must be an object")
    for field in ("python", "build_backend", "platform"):
        if not isinstance(build_context.get(field), str) or not build_context[field]:
            raise SupplyChainProvenanceError(f"build_context.{field} must be explicit")
    if not isinstance(record["build_steps"], list) or not record["build_steps"]:
        raise SupplyChainProvenanceError("build_steps must be a non-empty list")

    tests = record["security_tests"]
    if not isinstance(tests, list) or not tests:
        raise SupplyChainProvenanceError("security_tests must be a non-empty list")
    for test in tests:
        if not isinstance(test, dict):
            raise SupplyChainProvenanceError("security test record must be an object")
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
    if not isinstance(artifact, dict):
        raise SupplyChainProvenanceError("artifact must be an object")
    for field in ("name", "sha256", "size_bytes"):
        if field not in artifact:
            raise SupplyChainProvenanceError(f"artifact missing {field}")
    if (
        not isinstance(artifact["sha256"], str)
        or re.fullmatch(r"[0-9a-f]{64}", artifact["sha256"]) is None
    ):
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
    if not isinstance(verification, dict):
        raise SupplyChainProvenanceError("verification must be an object")
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
    """Verify one Tier 8 provenance record without regenerating source identity."""
    args = _parse_args()
    record = json.loads(args.provenance.read_text(encoding="utf-8"))
    validate_provenance_record(record, root=ROOT, artifact_path=args.artifact)
    print("tier8-supply-chain: VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
