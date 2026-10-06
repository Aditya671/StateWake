"""Verify StateWake package identity and release-version consistency."""

from __future__ import annotations

import ast
import sys
import tomllib
from pathlib import Path

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from scripts.common.project_metadata import load_project_metadata  # noqa: E402
from scripts.common.project_paths import PROJECT_ROOT  # noqa: E402

ROOT = PROJECT_ROOT
EXPECTED_API_CONTRACT_VERSION = "1"


def _package_constant(name: str) -> str:
    """Read one literal public package constant without importing the package."""
    metadata = load_project_metadata(ROOT)
    path = ROOT / metadata.package_init_relative
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
    raise AssertionError(f"missing package constant: {name}")


def current_version() -> str:
    """Read the authoritative project version from structured metadata."""
    return load_project_metadata(ROOT).version


def main() -> None:
    """Verify package, lock, CLI, and public API version identity semantically."""
    metadata = load_project_metadata(ROOT)
    with (ROOT / "pyproject.toml").open("rb") as stream:
        pyproject = tomllib.load(stream)
    with (ROOT / "uv.lock").open("rb") as stream:
        lock = tomllib.load(stream)

    project = pyproject["project"]
    distribution = str(project["name"])
    version = str(project["version"])
    package_version = _package_constant("__version__")
    api_contract_version = _package_constant("__public_api_contract_version__")
    normalized_distribution = metadata.distribution.lower().replace("_", "-")
    lock_project = next(
        (
            item
            for item in lock["package"]
            if str(item.get("name", "")).lower().replace("_", "-")
            == normalized_distribution
        ),
        None,
    )
    if lock_project is None:
        raise AssertionError(
            f"missing {metadata.distribution} project entry in uv.lock"
        )
    lock_version = str(lock_project.get("version", ""))

    assert distribution == metadata.distribution, distribution
    assert version == package_version == lock_version == current_version(), (
        version,
        package_version,
        lock_version,
    )
    assert api_contract_version == EXPECTED_API_CONTRACT_VERSION
    scripts = project.get("scripts")
    assert isinstance(scripts, dict)
    assert scripts.get(metadata.cli_name) == metadata.cli_target
    urls = project.get("urls")
    assert isinstance(urls, dict) and urls
    assert all(
        isinstance(value, str) and value.startswith("https://")
        for value in urls.values()
    )

    print(
        f"versioning: verified {distribution} {version} with import package "
        f"{metadata.import_package}"
    )


if __name__ == "__main__":
    main()
