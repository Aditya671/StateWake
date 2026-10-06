"""Regression coverage for the deterministic security-verifier frontier."""

from __future__ import annotations

import subprocess
import sys

from scripts.common.project_paths import PROJECT_ROOT

SECURITY_VERIFIERS = (
    "verify_security_assurance_boundary.py",
    "verify_cryptographic_trust_migration.py",
    "verify_data_lifecycle_confidentiality.py",
    "verify_forensic_continuity.py",
    "verify_identity_access_controls.py",
    "verify_recovery_resilience.py",
    "verify_runtime_containment.py",
    "verify_trust_domain_anchors.py",
)


def test_deterministic_security_verifiers_accept_current_candidate() -> None:
    """Maintained leaf security verifiers must execute successfully.

    Continuous-security orchestration is covered separately to avoid recursive
    assurance execution when this suite is itself selected for re-verification.
    """
    verifier_root = PROJECT_ROOT / "scripts" / "security"
    failures: list[str] = []
    for verifier in SECURITY_VERIFIERS:
        path = verifier_root / verifier
        completed = subprocess.run(
            [sys.executable, str(path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if completed.returncode != 0:
            failures.append(
                f"{verifier}: exit={completed.returncode}; "
                f"stdout={completed.stdout!r}; stderr={completed.stderr!r}"
            )
    assert not failures, "\n".join(failures)
