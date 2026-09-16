"""Execute deterministic release-candidate gates and emit release provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from config.project_paths import PROJECT_ROOT, VERIFICATION_PATH  # noqa: E402

ROOT = PROJECT_ROOT
EXPECTED_VERSION = "0.1.1"
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


def run_gate(name: str, command: Sequence[str], *, timeout: int) -> dict[str, object]:
    """Run one release gate and return machine-readable evidence."""
    completed = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    result: dict[str, object] = {
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
    """Return a deterministic digest of tracked release-source bytes."""
    digest = hashlib.sha256()
    excluded = {".git", ".pytest_cache", "__pycache__", "dist", "build"}
    paths = sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file() and not any(part in excluded for part in path.parts)
    )
    for path in paths:
        relative = path.relative_to(ROOT).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def static_contract() -> dict[str, object]:
    """Verify release identity and required release documentation locally."""
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    package = (ROOT / "src/statewake/__init__.py").read_text(encoding="utf-8")
    missing = [path for path in REQUIRED_DOCS if not (ROOT / path).is_file()]
    if 'version = "0.1.1"' not in pyproject:
        raise GateFailureError("release candidate version is not v0.1.1")
    if '__version__ = "0.1.1"' not in package:
        raise GateFailureError("package version is not 0.1.1")
    if missing:
        raise GateFailureError("missing release documents: " + ", ".join(missing))
    return {"name": "release-contract", "status": "passed", "missing": []}


def _parse_args() -> argparse.Namespace:
    """Parse release-candidate verification options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=VERIFICATION_PATH / "release-candidate-evidence.json",
    )
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--skip-build", action="store_true")
    return parser.parse_args()


def main() -> int:
    """Execute release gates and persist the resulting provenance record."""
    args = _parse_args()
    gates: list[dict[str, object]] = [static_contract()]
    commands = [
        ("versioning", [sys.executable, "scripts/release/verify_versioning.py"]),
        (
            "compatibility-fixtures",
            [sys.executable, "-m", "pytest", "tests/test_compatibility_fixtures.py"],
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
    try:
        for name, command in commands:
            gates.append(run_gate(name, command, timeout=args.timeout))
    except (GateFailureError, subprocess.TimeoutExpired) as exc:
        record = {
            "status": "failed",
            "version": EXPECTED_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "source_tree_sha256": tree_digest(),
            "gates": gates,
            "failure": str(exc),
        }
        output = ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(record, sort_keys=True))
        return 1

    record = {
        "status": "passed",
        "version": EXPECTED_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "source_tree_sha256": tree_digest(),
        "gates": gates,
        "approval": "human-release-approval-required",
        "publication_authorized": False,
    }
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(record, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
