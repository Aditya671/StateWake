"""Execute deterministic release-candidate gates and emit release provenance."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from scripts.common.project_paths import PROJECT_ROOT, VERIFICATION_PATH  # noqa: E402
from scripts.common.release_identity import (  # noqa: E402
    refresh_release_identity,
    source_tree_digest,
    validate_release_identity,
)
from scripts.release import verify_supply_chain_provenance as supply_chain  # noqa: E402

ROOT = PROJECT_ROOT
REQUIRED_DOCS = (
    "docs/user-guide/index.md",
    "docs/user-guide/release.md",
    "docs/user-guide/limitations.md",
    "docs/user-guide/release-evidence-index.md",
    "docs/governance/RELEASE_GOVERNANCE.md",
    "docs/governance/RELEASE_READINESS.md",
    "docs/SDLC.md",
    "docs/QUALITY_GATES.md",
    "docs/DEFINITION_OF_DONE.md",
    "docs/governance/REPOSITORY_STRUCTURE.md",
)


class GateFailureError(RuntimeError):
    """Raised when an executable release gate fails."""


def run_gate(
    name: str,
    command: Sequence[str],
    *,
    timeout: int | None,
) -> dict[str, object]:
    """Run one release gate and return machine-readable evidence."""
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        result: dict[str, object] = {
            "name": name,
            "command": list(command),
            "status": "timed_out",
            "timeout_seconds": timeout,
            "stdout": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
        }
        raise GateFailureError(json.dumps(result, sort_keys=True)) from exc
    result = {
        "name": name,
        "command": list(command),
        "returncode": completed.returncode,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
        "status": "passed" if completed.returncode == 0 else "failed",
    }
    if completed.returncode != 0:
        raise GateFailureError(json.dumps(result, sort_keys=True))
    return result


def tree_digest() -> str:
    """Return the canonical deterministic digest of release-source bytes."""
    return source_tree_digest(ROOT)


def static_contract() -> dict[str, object]:
    """Verify structured release identity and required release-document inventory."""
    metadata = supply_chain.project_metadata(ROOT)
    missing = [path for path in REQUIRED_DOCS if not (ROOT / path).is_file()]
    if missing:
        raise GateFailureError("missing release documents: " + ", ".join(missing))
    return {
        "name": "release-contract",
        "status": "passed",
        "distribution": metadata["distribution"],
        "version": metadata["version"],
        "missing": [],
    }


def _parse_args() -> argparse.Namespace:
    """Parse release-candidate verification options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=VERIFICATION_PATH / "release-candidate-evidence.json",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Per-gate timeout in seconds; use 0 to disable process timeouts.",
    )
    parser.add_argument("--skip-build", action="store_true")
    return parser.parse_args()


def _timeout(value: int) -> int | None:
    return None if value == 0 else value


def main() -> int:
    """Refresh identity, execute release gates, and persist provenance evidence."""
    args = _parse_args()
    gates: list[dict[str, object]] = []
    try:
        identity = refresh_release_identity(ROOT)
        gates.append(
            {"name": "release-identity-refresh", "status": "passed", **identity}
        )
        validate_release_identity(ROOT)
        gates.append({"name": "release-identity-verify", "status": "passed"})
        gates.append(static_contract())
    except (GateFailureError, ValueError) as exc:
        preflight_failure = str(exc)
        record: dict[str, Any] = {
            "status": "failed",
            "generated_at": datetime.now(UTC).isoformat(),
            "source_tree_sha256": tree_digest(),
            "gates": gates,
            "failure": preflight_failure,
            "publication_authorized": False,
        }
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(record, sort_keys=True))
        return 1

    commands = [
        ("versioning", [sys.executable, "scripts/release/verify_versioning.py"]),
        (
            "compatibility-fixtures",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_compatibility_fixtures.py",
            ],
        ),
        (
            "product-experience",
            [sys.executable, "scripts/release/verify_product_experience.py"],
        ),
        (
            "source-compilation",
            [sys.executable, "-m", "compileall", "-q", "src", "tests", "scripts"],
        ),
    ]
    if not args.skip_build:
        commands.append(("build", ["uv", "build", "--wheel"]))
        commands.append(
            (
                "package-boundary",
                [sys.executable, "scripts/release/verify_package_boundary.py", "dist"],
            )
        )
    failure: str | None = None
    try:
        for name, command in commands:
            gates.append(run_gate(name, command, timeout=_timeout(args.timeout)))
    except GateFailureError as exc:
        failure = str(exc)

    metadata = supply_chain.project_metadata(ROOT)
    record = {
        "status": "passed" if failure is None else "failed",
        "version": metadata["version"],
        "generated_at": datetime.now(UTC).isoformat(),
        "source_tree_sha256": tree_digest(),
        "gates": gates,
        "failure": failure,
        "approval": "human-release-approval-required",
        "publication_authorized": False,
    }
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(record, sort_keys=True))
    return 0 if failure is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
