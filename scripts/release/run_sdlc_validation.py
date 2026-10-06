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

from scripts.common.project_paths import PROJECT_ROOT  # noqa: E402

ROOT: Final[Path] = PROJECT_ROOT
LONG_RUNNING_GATES: Final[frozenset[str]] = frozenset(
    {
        "unit-and-integration-tests",
        "property-state-machine",
        "real-world-validation",
        "chaos-validation",
        "deep-chaos-validation",
        "extreme-validation",
        "failure-lab",
        "public-trial-regressions",
        "continuous-security-assurance",
        "release-candidate",
    }
)


class GateFailureError(RuntimeError):
    """Raised when an SDLC gate fails."""


def command_plan(profile: str) -> list[tuple[str, list[str]]]:
    """Return ordered verification gates for a workflow profile."""
    python = sys.executable
    common = [
        (
            "validation-state-stabilization",
            [python, "scripts/release/prepare_sdlc_validation.py"],
        ),
        (
            "release-identity-verify",
            [python, "scripts/release/verify_release_identity.py"],
        ),
        (
            "repository-structure",
            [python, "scripts/release/verify_repository_structure.py"],
        ),
        ("version-identity", [python, "scripts/release/verify_versioning.py"]),
        ("source-quality", [python, "scripts/development/verify_source_quality.py"]),
        (
            "ruff-check",
            [python, "-m", "ruff", "check", "src", "tests", "scripts", "examples"],
        ),
        (
            "ruff-format",
            [
                python,
                "-m",
                "ruff",
                "format",
                "--check",
                "src",
                "tests",
                "scripts",
                "examples",
            ],
        ),
        ("strict-typecheck", [python, "-m", "mypy"]),
        (
            "source-compilation",
            [python, "-m", "compileall", "-q", "src", "tests", "scripts", "examples"],
        ),
        ("unit-and-integration-tests", [python, "-m", "pytest"]),
        (
            "product-experience",
            [python, "scripts/release/verify_product_experience.py"],
        ),
        ("cli-surface", [python, "scripts/release/verify_cli_surface.py"]),
        (
            "post-check-release-identity-verify",
            [python, "scripts/release/verify_release_identity.py"],
        ),
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
        (
            "public-trial-regressions",
            [python, "scripts/testing/run_public_trial_regressions.py"],
        ),
        (
            "continuous-security-assurance",
            [
                python,
                "scripts/security/verify_continuous_security_assurance.py",
                "--promote-on-success",
            ],
        ),
        (
            "final-release-identity-refresh",
            [python, "scripts/release/refresh_release_identity.py"],
        ),
        (
            "final-release-identity-verify",
            [python, "scripts/release/verify_release_identity.py"],
        ),
        ("release-candidate", [python, "scripts/release/verify_release_candidate.py"]),
    ]


def _gate_timeout(name: str, base_timeout: int) -> int | None:
    """Return a gate-specific timeout; zero disables subprocess timeouts."""
    if base_timeout == 0:
        return None
    return base_timeout * 3 if name in LONG_RUNNING_GATES else base_timeout


def _run(name: str, command: list[str], timeout: int | None) -> dict[str, object]:
    """Execute one gate from the repository root and return structured evidence."""
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
            "command": command,
            "status": "timed_out",
            "timeout_seconds": timeout,
            "stdout": (exc.stdout or "")[-3000:] if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "")[-3000:] if isinstance(exc.stderr, str) else "",
        }
        raise GateFailureError(json.dumps(result, sort_keys=True)) from exc
    result = {
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
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Base per-gate timeout in seconds; use 0 to disable process timeouts.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    gates: list[dict[str, object]] = []
    status = "passed"
    failure = None
    try:
        for name, command in command_plan(args.profile):
            gates.append(_run(name, command, _gate_timeout(name, args.timeout)))
    except GateFailureError as exc:
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
