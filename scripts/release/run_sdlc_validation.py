"""Run the StateWake software-development lifecycle verification gates."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from config.project_paths import PROJECT_ROOT  # noqa: E402

ROOT: Final[Path] = PROJECT_ROOT


class GateFailureError(RuntimeError):
    """Raised when an SDLC gate fails."""


def command_plan(profile: str) -> list[tuple[str, list[str]]]:
    """Return the ordered, reusable verification gates for a workflow profile."""
    python = sys.executable
    common = [
        (
            "repository-structure",
            [python, "scripts/release/verify_repository_structure.py"],
        ),
        ("version-identity", [python, "scripts/release/verify_versioning.py"]),
        ("source-quality", [python, "scripts/development/verify_source_quality.py"]),
        ("ruff-check", [python, "-m", "ruff", "check", "src", "tests", "scripts"]),
        (
            "ruff-format",
            [python, "-m", "ruff", "format", "--check", "src", "tests", "scripts"],
        ),
        ("strict-typecheck", ["uv", "run", "pyright"]),
        (
            "source-compilation",
            [python, "-m", "compileall", "-q", "src", "tests", "scripts"],
        ),
        ("unit-and-integration-tests", [python, "-m", "pytest"]),
        (
            "product-experience",
            [python, "scripts/release/verify_product_experience.py"],
        ),
        ("cli-surface", [python, "scripts/release/verify_cli_surface.py"]),
    ]
    if profile == "check":
        return common
    return common + [
        (
            "property-state-machine",
            [python, "scripts/testing/property_state_machine.py"],
        ),
        (
            "real-world-validation",
            [python, "scripts/testing/run_real_world_scenarios.py"],
        ),
        ("chaos-validation", [python, "scripts/testing/run_chaos_validation.py"]),
        (
            "deep-chaos-validation",
            [python, "scripts/testing/run_deep_chaos_validation.py"],
        ),
        ("extreme-validation", [python, "scripts/testing/run_extreme_validation.py"]),
        ("failure-lab", [python, "scripts/testing/failure_lab.py", "--ci"]),
        (
            "external-integration-fixtures",
            [
                python,
                "scripts/integration/run_external_integrations.py",
                "--mode",
                "ci",
            ],
        ),
        ("release-candidate", [python, "scripts/release/verify_release_candidate.py"]),
    ]


def _run(name: str, command: list[str], timeout: int) -> dict[str, object]:
    """Execute one gate from the repository root and return structured evidence."""
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
        "command": command,
        "returncode": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "stdout": completed.stdout[-3000:],
        "stderr": completed.stderr[-3000:],
    }
    if completed.returncode:
        raise GateFailureError(json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    """Run the selected SDLC profile and emit machine-readable evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("check", "release"), default="check")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    gates: list[dict[str, object]] = []
    status = "passed"
    failure = None
    try:
        for name, command in command_plan(args.profile):
            gates.append(_run(name, command, args.timeout))
    except (GateFailureError, subprocess.TimeoutExpired) as exc:
        status = "failed"
        failure = str(exc)

    record = {
        "workflow": "statewake-sdlc",
        "profile": args.profile,
        "status": status,
        "generated_at": datetime.now(UTC).isoformat(),
        "gates": gates,
        "failure": failure,
        "publication_authorized": False,
    }
    if args.output:
        output = (
            (ROOT / args.output).resolve()
            if not args.output.is_absolute()
            else args.output
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(record, sort_keys=True))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
