"""Verify the StateWake repository structure and active naming boundary."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from config.project_paths import PROJECT_ROOT  # noqa: E402
from scripts.common.release_scope import release_input_files  # noqa: E402

ROOT: Final[Path] = PROJECT_ROOT
EXPECTED_DIRECTORIES: Final[tuple[str, ...]] = (
    "config",
    "data",
    "docs/user-guide",
    "docs/reference",
    "docs/architecture",
    "docs/specifications",
    "docs/development",
    "docs/testing",
    "docs/security",
    "docs/operations",
    "docs/governance",
    "docs/integrations",
    "docs/examples",
    "docs/adr",
    "scripts/common",
    "scripts/development",
    "scripts/testing",
    "scripts/integration",
    "scripts/release",
    "src/statewake",
    "tests",
    "tests/fixtures/external_captures",
)
FORBIDDEN_PATHS: Final[tuple[str, ...]] = (
    "docs/release-artifact-docs",
    "docs/specs",
    "docs/external-integrations",
    "docs/github-server-settings",
    "scripts/failure_lab.py",
    "scripts/property_state_machine.py",
    "scripts/run_chaos_validation.py",
    "scripts/run_deep_chaos_validation.py",
    "scripts/run_extreme_validation.py",
    "scripts/run_real_world_scenarios.py",
    "scripts/run_external_integrations.py",
    "scripts/verify_cli_surface.py",
    "scripts/verify_package_boundary.py",
    "scripts/verify_product_experience.py",
    "scripts/verify_release_candidate.py",
    "scripts/verify_repository_governance.py",
    "scripts/verify_source_quality.py",
    "scripts/verify_versioning.py",
    "scripts/validation_storage.py",
    "scripts/external_captures",
    "scripts/initialize_local_database.py",
    "chaos_probe.py",
)
FORBIDDEN_IDENTIFIERS: Final[tuple[str, ...]] = (
    "Ke" + "el",
    "KE" + "EL",
    "keel" + "_ai",
    "keel" + "-ai",
    "Anchor" + "line",
)


def main() -> int:
    """Verify expected directories, forbidden paths, and obsolete project identities."""
    failures: list[str] = []
    for directory in EXPECTED_DIRECTORIES:
        if not (ROOT / directory).is_dir():
            failures.append(f"missing expected directory: {directory}")
    for forbidden_path in FORBIDDEN_PATHS:
        if (ROOT / forbidden_path).exists():
            failures.append(f"obsolete repository path exists: {forbidden_path}")

    for candidate in release_input_files(ROOT):
        if candidate.suffix.lower() not in {".md", ".py", ".txt", ".yml", ".yaml"}:
            continue
        text = candidate.read_text(encoding="utf-8")
        for identifier in FORBIDDEN_IDENTIFIERS:
            if identifier in text:
                failures.append(
                    f"obsolete project identity {identifier!r}: {candidate.relative_to(ROOT)}"
                )
    if failures:
        print("REPOSITORY STRUCTURE: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("REPOSITORY STRUCTURE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
