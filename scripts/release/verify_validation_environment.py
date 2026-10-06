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


def _requirement_name(requirement: str) -> str:
    """Return the distribution name from a PEP 508-style requirement string."""
    match = _REQUIREMENT_NAME.match(requirement.strip())
    if match is None:
        raise ValueError(
            f"cannot determine distribution name from requirement: {requirement!r}"
        )
    return match.group(0)


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


def validation_environment_status(root: Path = ROOT) -> dict[str, object]:
    """Return installed-version evidence for the canonical validation profile."""
    required = required_validation_distributions(root)
    installed: dict[str, str] = {}
    missing: list[str] = []
    for name in required:
        try:
            installed[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)
    return {
        "status": "verified" if not missing else "missing_dependencies",
        "python": sys.version.split()[0],
        "python_executable": sys.executable,
        "required_distributions": list(required),
        "installed_versions": installed,
        "missing_distributions": missing,
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
