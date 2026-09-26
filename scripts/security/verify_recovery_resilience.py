"""Verify Tier 6 recovery and resilience assurance evidence consistency."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REQUIRED_DOCUMENTS = (
    "docs/security/recovery_resilience_assurance.md",
    "docs/security/INCIDENT_RECOVERY.md",
    "docs/operations/OPERATIONS_STATE_RECOVERY.md",
    "docs/specifications/reconciliation-recovery-v0.1.md",
    "docs/security/continuous_security_assurance.md",
)
REQUIRED_RUNTIME_REFS = (
    "src/statewake/adapters/reliability_state.py",
    "src/statewake/services/persistence.py",
    "src/statewake/services/reliability_recovery_service.py",
    "src/statewake/domain/provenance.py",
    "src/statewake/domain/trust_anchor.py",
    "src/statewake/adapters/key_management.py",
)
REQUIRED_TEST_NAMES = (
    "test_mode_a_evidence_corruption_recovery",
    "test_mode_b_provenance_corruption_recovery",
    "test_mode_c_state_history_corruption_recovery",
    "test_mode_d_checkpoint_disagreement_is_not_silently_repaired",
    "test_mode_e_key_compromise_revoke_rotate",
    "test_interrupted_recovery_never_marks_success",
    "test_partial_failure_does_not_promote_unverified_state",
    "test_post_recovery_verification_is_mandatory",
)
REQUIRED_TERMS = (
    "independent trusted source",
    "verified canonical evidence",
    "validated durable state",
    "derived local views",
    "caches / transient observations",
    "Mode A",
    "Mode B",
    "Mode C",
    "Mode D",
    "Mode E",
    "Recovery non-invention invariant",
    "post-recovery verification",
    "not a release approval",
)


@dataclass(frozen=True, slots=True)
class Finding:
    """Represent one verifier finding."""

    category: str
    detail: str


def _exists(root: Path, relative: str) -> bool:
    return (root / relative).is_file()


def verify(root: Path) -> tuple[Finding, ...]:
    """Return deterministic findings for Tier 6 evidence consistency."""
    findings: list[Finding] = []
    for relative in (*REQUIRED_DOCUMENTS, *REQUIRED_RUNTIME_REFS):
        if not _exists(root, relative):
            findings.append(Finding("missing-file", relative))

    tier6_path = root / "docs/security/recovery_resilience_assurance.md"
    if tier6_path.is_file():
        text = tier6_path.read_text(encoding="utf-8")
        for term in REQUIRED_TERMS:
            if term.lower() not in text.lower():
                findings.append(Finding("missing-semantic-term", term))

    test_path = root / "tests/security/test_recovery_resilience.py"
    if not test_path.is_file():
        findings.append(Finding("missing-test-suite", str(test_path)))
    else:
        test_text = test_path.read_text(encoding="utf-8")
        for name in REQUIRED_TEST_NAMES:
            if f"def {name}" not in test_text:
                findings.append(Finding("missing-regression", name))

    recovery_service = root / "src/statewake/services/reliability_recovery_service.py"
    if recovery_service.is_file():
        text = recovery_service.read_text(encoding="utf-8")
        required = (
            "verify_reliability_recovery_outcome",
            "recovery artifact digest mismatch",
            "recovered reliability outcome requires",
        )
        for term in required:
            if term not in text:
                findings.append(Finding("missing-recovery-invariant", term))

    state_store = root / "src/statewake/adapters/reliability_state.py"
    if state_store.is_file():
        text = state_store.read_text(encoding="utf-8")
        for term in (
            "previous transition digest",
            "stored transition digest mismatch",
            "_recover_partial_tail",
        ):
            if term not in text:
                findings.append(Finding("missing-state-invariant", term))

    if (root / "pyproject.toml").is_file():
        import tomllib

        pyproject_path = root / "pyproject.toml"
        pyproject = pyproject_path.read_text(encoding="utf-8")
        project = tomllib.loads(pyproject)["project"]
        project_version = str(project["version"])
        package = (root / "src/statewake/__init__.py").read_text(encoding="utf-8")
        if f'__version__ = "{project_version}"' not in package:
            findings.append(
                Finding("release-boundary", "package version is not synchronized")
            )

    return tuple(findings)


def run_tests(root: Path) -> int:
    """Run only the Tier 6 focused regression suite."""
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/security/test_recovery_resilience.py",
            "-q",
        ],
        cwd=root,
        check=False,
    )
    return completed.returncode


def main() -> int:
    """Run the Tier 6 evidence verifier."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    findings = verify(args.root.resolve())
    if findings:
        print("RECOVERY RESILIENCE ASSURANCE: FAIL")
        for item in findings:
            print(f"- [{item.category}] {item.detail}")
        return 1
    print("RECOVERY RESILIENCE ASSURANCE: PASS")
    if args.run_tests:
        return run_tests(args.root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
