"""Verify StateWake package identity and release-version consistency."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from config.project_paths import PROJECT_ROOT  # noqa: E402

ROOT = PROJECT_ROOT
EXPECTED_VERSION = "0.1.1"
EXPECTED_DISTRIBUTION = "statewake-ai"
EXPECTED_IMPORT_PACKAGE = "statewake"
EXPECTED_API_CONTRACT_VERSION = "1"


def read(path: str) -> str:
    """Read a UTF-8 project file relative to the repository root."""
    return (ROOT / path).read_text(encoding="utf-8")


def extract(pattern: str, text: str, label: str) -> str:
    """Extract one required metadata value and fail clearly when it is absent."""
    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        raise AssertionError(f"missing {label}")
    return match.group(1)


def main() -> None:
    """Verify the distribution, import namespace, executable, and documented release version."""
    pyproject = read("pyproject.toml")
    package = read("src/statewake/__init__.py")
    lock = read("uv.lock")
    changelog = read("CHANGELOG.md")
    readme = read("README.md")

    distribution = extract(r'^name = "([^"]+)"', pyproject, "distribution name")
    version = extract(r'^version = "([^"]+)"', pyproject, "project version")
    package_version = extract(r'^__version__ = "([^"]+)"', package, "package version")
    api_contract_version = extract(
        r'^__public_api_contract_version__ = "([^"]+)"',
        package,
        "public API contract version",
    )
    project_match = re.search(
        r'(?ms)^\[\[package\]\]\nname = "statewake-ai"\nversion = "([^"]+)"',
        lock,
    )
    if project_match is None:
        raise AssertionError("missing statewake-ai project entry in uv.lock")
    lock_version = project_match.group(1)

    assert distribution == EXPECTED_DISTRIBUTION, distribution
    assert version == package_version == lock_version == EXPECTED_VERSION, (
        version,
        package_version,
        lock_version,
    )
    assert api_contract_version == EXPECTED_API_CONTRACT_VERSION
    assert 'statewake = "statewake.cli.main:main"' in pyproject
    assert "## [v0.1.1]" in changelog
    assert "public package baseline is **v0.1.1**" in readme
    assert "statewake-ai" in readme
    assert "https://github.com/Aditya671/StateWake" in readme
    assert "https://github.com/Aditya671/StateWake/tree/main/docs/user-guide" in readme
    assert "(docs/user-guide/)" not in readme
    print(
        f"versioning: verified {distribution} {version} with import package {EXPECTED_IMPORT_PACKAGE}"
    )


if __name__ == "__main__":
    main()
