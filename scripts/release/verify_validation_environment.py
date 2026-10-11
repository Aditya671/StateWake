"""Verify that the locked StateWake validation dependency profile is installed."""

from __future__ import annotations

import importlib.metadata
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Final

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from scripts.common.project_paths import PROJECT_ROOT  # noqa: E402

ROOT: Final[Path] = PROJECT_ROOT
_REQUIREMENT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")
_NORMALIZE_NAME = re.compile(r"[-_.]+")


def _requirement_name(requirement: str) -> str:
    """Return the distribution name from a PEP 508-style requirement string."""
    match = _REQUIREMENT_NAME.match(requirement.strip())
    if match is None:
        raise ValueError(
            f"cannot determine distribution name from requirement: {requirement!r}"
        )
    return match.group(0)


def _canonical_name(name: str) -> str:
    """Return a PEP 503-style canonical distribution name without extra dependencies."""
    return _NORMALIZE_NAME.sub("-", name).lower()


def required_validation_distributions(root: Path = ROOT) -> tuple[str, ...]:
    """Return distributions required by the canonical dev + integrations profile."""
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    groups = data.get("dependency-groups", {})
    optional = data.get("project", {}).get("optional-dependencies", {})
    dev = groups.get("dev")
    integrations = optional.get("integrations")
    if not isinstance(dev, list) or not all(isinstance(item, str) for item in dev):
        raise ValueError(
            "pyproject.toml must define dependency-groups.dev as string requirements"
        )
    if not isinstance(integrations, list) or not all(
        isinstance(item, str) for item in integrations
    ):
        raise ValueError(
            "pyproject.toml must define project.optional-dependencies.integrations "
            "as string requirements"
        )
    return tuple(
        sorted(
            {_requirement_name(item) for item in (*dev, *integrations)}, key=str.lower
        )
    )


def locked_distribution_versions(root: Path = ROOT) -> dict[str, tuple[str, ...]]:
    """Return exact locked versions keyed by canonical distribution name."""
    lock_path = root / "uv.lock"
    if not lock_path.is_file():
        raise ValueError("uv.lock is missing")
    data = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    packages = data.get("package")
    if not isinstance(packages, list):
        raise ValueError("uv.lock must contain package records")
    versions: dict[str, set[str]] = {}
    for record in packages:
        if not isinstance(record, dict):
            raise ValueError("uv.lock contains an invalid package record")
        name = record.get("name")
        version = record.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            raise ValueError("uv.lock package records must contain name and version")
        versions.setdefault(_canonical_name(name), set()).add(version)
    return {name: tuple(sorted(values)) for name, values in versions.items()}


def validation_environment_status(root: Path = ROOT) -> dict[str, object]:
    """Return installed-version evidence for the locked validation profile."""
    required = required_validation_distributions(root)
    locked = locked_distribution_versions(root)
    installed: dict[str, str] = {}
    locked_versions: dict[str, list[str]] = {}
    missing: list[str] = []
    missing_from_lock: list[str] = []
    mismatched: dict[str, dict[str, object]] = {}
    for name in required:
        canonical = _canonical_name(name)
        expected = locked.get(canonical)
        if expected is None:
            missing_from_lock.append(name)
        else:
            locked_versions[name] = list(expected)
        try:
            version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
            continue
        installed[name] = version
        if expected is not None and version not in expected:
            mismatched[name] = {"installed": version, "locked": list(expected)}
    verified = not missing and not missing_from_lock and not mismatched
    return {
        "status": "verified" if verified else "invalid_environment",
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "required_distributions": list(required),
        "installed_versions": installed,
        "locked_versions": locked_versions,
        "missing_distributions": missing,
        "missing_from_lock": missing_from_lock,
        "version_mismatches": mismatched,
    }


def main() -> int:
    """Verify the current interpreter environment and emit machine-readable evidence."""
    try:
        result = validation_environment_status()
    except ValueError as exc:
        print(json.dumps({"status": "failed", "failure": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
