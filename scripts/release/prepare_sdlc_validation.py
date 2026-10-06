"""Prepare deterministic StateWake validation state without hiding source drift.

This preflight refreshes only generated release identity in the repository and
stabilizes the current Python environment from the already-locked validation
profile. It deliberately does not rewrite dependency locks, current
source/document boundaries, or the continuous-security baseline. Those artifacts
have independent governance and must fail closed when stale or inconsistent.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Final

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from scripts.common.project_paths import PROJECT_ROOT  # noqa: E402
from scripts.common.release_identity import (  # noqa: E402
    refresh_release_identity,
    validate_release_identity,
)

ROOT: Final[Path] = PROJECT_ROOT


class ValidationPreparationError(RuntimeError):
    """Raised when deterministic validation preparation cannot converge."""


def _run_check(name: str, command: list[str], *, timeout: int) -> dict[str, object]:
    """Run one bounded preparation step and return structured evidence."""
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
        raise ValidationPreparationError(f"{name} timed out after {timeout}s") from exc
    result: dict[str, object] = {
        "name": name,
        "command": command,
        "returncode": completed.returncode,
        "status": "passed" if completed.returncode == 0 else "failed",
        "stdout": completed.stdout[-3000:],
        "stderr": completed.stderr[-3000:],
    }
    if completed.returncode != 0:
        raise ValidationPreparationError(json.dumps(result, sort_keys=True))
    return result


def prepare_validation_state(*, timeout: int = 180) -> dict[str, object]:
    """Refresh safe generated state and verify governed non-generated state.

    Release identity is derived entirely from the current maintained source
    boundary, so refreshing it is safe and deterministic. The current Python
    environment is synchronized from the existing lock with the canonical dev +
    integrations profile. Dependency locks and the continuous-security baseline
    are *verified*, never silently rewritten.
    """
    identity = refresh_release_identity(ROOT)
    validate_release_identity(ROOT)
    checks = [
        _run_check(
            "uv-lock-check",
            ["uv", "lock", "--check", "--python", sys.executable],
            timeout=timeout,
        ),
        _run_check(
            "validation-environment-sync",
            [
                "uv",
                "sync",
                "--locked",
                "--python",
                sys.executable,
                "--group",
                "dev",
                "--extra",
                "integrations",
            ],
            timeout=timeout,
        ),
        _run_check(
            "validation-environment-verify",
            [sys.executable, "scripts/release/verify_validation_environment.py"],
            timeout=timeout,
        ),
        _run_check(
            "continuous-security-assurance",
            [
                sys.executable,
                "scripts/security/verify_continuous_security_assurance.py",
            ],
            timeout=timeout,
        ),
    ]
    return {
        "status": "stabilized",
        "release_identity": identity,
        "checks": checks,
        "mutated_authorities": [
            "verification_manifest.txt",
            "candidate-fingerprint.txt",
        ],
        "stabilized_environment": [
            "locked dependency group: dev",
            "locked optional extra: integrations",
        ],
        "not_auto_refreshed": [
            "uv.lock",
            "ui/package-lock.json",
            "docs/security/security_assurance_baseline_manifest.txt",
            "maintained source and documentation",
        ],
    }


def main() -> int:
    """Prepare the current checkout for SDLC validation and emit JSON evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Timeout in seconds for each non-mutating preparation check.",
    )
    args = parser.parse_args()
    try:
        result = prepare_validation_state(timeout=args.timeout)
    except (ValidationPreparationError, ValueError) as exc:
        print(json.dumps({"status": "failed", "failure": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
