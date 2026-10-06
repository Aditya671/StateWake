"""Verify Tier 6 recovery/resilience assurance structure."""

from __future__ import annotations

import argparse
import ast
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


@dataclass(frozen=True, slots=True)
class Finding:
    """Represent one verifier finding."""

    category: str
    detail: str


def _defined_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }


def verify(root: Path) -> tuple[Finding, ...]:
    """Return deterministic structural findings for Tier 6 assurance."""
    findings: list[Finding] = []
    for relative in (*REQUIRED_DOCUMENTS, *REQUIRED_RUNTIME_REFS):
        path = root / relative
        if not path.is_file():
            findings.append(Finding("missing-file", relative))
        elif relative.startswith("docs/") and path.stat().st_size == 0:
            findings.append(Finding("empty-document", relative))

    test_path = root / "tests/security/test_recovery_resilience.py"
    if not test_path.is_file():
        findings.append(Finding("missing-test-suite", str(test_path)))
    else:
        test_names = _defined_names(test_path)
        findings.extend(
            Finding("missing-regression", name)
            for name in REQUIRED_TEST_NAMES
            if name not in test_names
        )

    recovery_service = root / "src/statewake/services/reliability_recovery_service.py"
    if recovery_service.is_file():
        names = _defined_names(recovery_service)
        for required in ("verify_reliability_recovery_outcome",):
            if required not in names:
                findings.append(Finding("missing-recovery-invariant", required))

    state_store = root / "src/statewake/adapters/reliability_state.py"
    if state_store.is_file() and "_recover_partial_tail" not in _defined_names(
        state_store
    ):
        findings.append(Finding("missing-state-invariant", "_recover_partial_tail"))

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
    root = args.root.resolve()
    findings = verify(root)
    if findings:
        print("RECOVERY RESILIENCE ASSURANCE: FAIL")
        for item in findings:
            print(f"- [{item.category}] {item.detail}")
        return 1
    print("RECOVERY RESILIENCE ASSURANCE: PASS")
    if args.run_tests:
        return run_tests(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
