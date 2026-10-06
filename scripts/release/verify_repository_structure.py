"""Verify the StateWake repository's maintained structural authority boundary."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from scripts.common.project_metadata import load_project_metadata  # noqa: E402
from scripts.common.project_paths import PROJECT_ROOT  # noqa: E402
from scripts.common.release_scope import (  # noqa: E402
    release_input_files,
    repository_files,
)

ROOT: Final[Path] = PROJECT_ROOT
METADATA = load_project_metadata(ROOT)
REQUIRED_PATHS: Final[tuple[str, ...]] = (
    "pyproject.toml",
    "uv.lock",
    METADATA.package_init_relative.as_posix(),
    "scripts/common/project_paths.py",
    "scripts/common/release_scope.py",
    "scripts/common/release_identity.py",
    "scripts/release/run_sdlc_validation.py",
    "scripts/release/prepare_sdlc_validation.py",
    "scripts/release/refresh_release_identity.py",
    "scripts/release/verify_release_identity.py",
    "tests",
    "examples",
    "docs",
    "docs/operations/workspace-production-operations.md",
    "docs/operations/workspace-backend-migration.md",
    "data/README.md",
)

RETIRED_PATHS: Final[tuple[str, ...]] = (
    "config",
    "docs/__init__.py",
    "docs/examples",
    "docs/workspace-backend-migration.md",
    "docs/workspace-production-operations.md",
)
SEQUENCE_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?:^|/)(?:phase|tier)[-_]?\d", re.IGNORECASE
)


def main() -> int:
    """Verify required authorities and reject duplicate top-level Python scripts."""
    failures: list[str] = []
    for relative in REQUIRED_PATHS:
        if not (ROOT / relative).exists():
            failures.append(f"missing maintained project authority: {relative}")

    for relative in RETIRED_PATHS:
        if (ROOT / relative).exists():
            failures.append(f"retired repository path is still present: {relative}")

    python_in_docs = sorted(
        path.relative_to(ROOT).as_posix() for path in (ROOT / "docs").rglob("*.py")
    )
    if python_in_docs:
        failures.append(
            "executable Python belongs outside docs/: " + ", ".join(python_in_docs)
        )

    placeholders = sorted(
        path.relative_to(ROOT).as_posix()
        for path in repository_files(ROOT)
        if path.name in {".gitkeep", ".keep"}
    )
    if placeholders:
        failures.append(
            "placeholder-only files must be replaced by an explicit boundary or removed: "
            + ", ".join(placeholders)
        )

    scripts_root = ROOT / "scripts"
    duplicate_top_level = sorted(
        path.relative_to(ROOT).as_posix()
        for path in scripts_root.glob("*.py")
        if path.name != "__init__.py"
    )
    if duplicate_top_level:
        failures.append(
            "top-level scripts duplicate categorized authorities: "
            + ", ".join(duplicate_top_level)
        )

    inputs = release_input_files(ROOT)
    if not inputs:
        failures.append("release-input scope selected no maintained files")
    if any(path.is_symlink() for path in inputs):
        failures.append("release-input scope unexpectedly contains symlinks")

    sequence_named_inputs = sorted(
        path.relative_to(ROOT).as_posix()
        for path in inputs
        if SEQUENCE_NAME_PATTERN.search(path.relative_to(ROOT).as_posix())
    )
    if sequence_named_inputs:
        failures.append(
            "active release inputs use development-sequence names: "
            + ", ".join(sequence_named_inputs)
        )

    if failures:
        print("REPOSITORY STRUCTURE: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"REPOSITORY STRUCTURE: PASS ({len(inputs)} release inputs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
