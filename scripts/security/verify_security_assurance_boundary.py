"""Verify the maintained StateWake security-assurance boundary structurally."""

from __future__ import annotations

import ast
from pathlib import Path

REQUIRED_SECURITY_DOCS = (
    "docs/security/THREAT_MODEL.md",
    "docs/security/CONTROL_TEST_MATRIX.md",
    "docs/security/INCIDENT_RECOVERY.md",
    "docs/security/security_assurance_boundary.md",
    "docs/adr/0004-security-architecture.md",
)
REQUIRED_SECURITY_TESTS = (
    "tests/security/test_continuous_security_assurance.py",
    "tests/security/test_cryptographic_trust_migration.py",
    "tests/security/test_data_lifecycle_confidentiality.py",
    "tests/security/test_identity_access_controls.py",
    "tests/security/test_recovery_resilience.py",
    "tests/security/test_runtime_containment.py",
    "tests/security/test_trust_domain_anchors.py",
)
REQUIRED_SECURITY_SCRIPTS = (
    "scripts/security/verify_continuous_security_assurance.py",
    "scripts/security/verify_cryptographic_trust_migration.py",
    "scripts/security/verify_data_lifecycle_confidentiality.py",
    "scripts/security/verify_identity_access_controls.py",
    "scripts/security/verify_recovery_resilience.py",
    "scripts/security/verify_runtime_containment.py",
    "scripts/security/verify_trust_domain_anchors.py",
)


def _python_syntax_findings(root: Path, relative_paths: tuple[str, ...]) -> list[str]:
    findings: list[str] = []
    for relative in relative_paths:
        path = root / relative
        if not path.is_file():
            findings.append(f"missing maintained security executable: {relative}")
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            findings.append(
                f"invalid security executable syntax: {relative}:{exc.lineno}"
            )
    return findings


def verify_security_assurance_boundary(project_root: Path) -> list[str]:
    """Return structural assurance findings; an empty list means boundary is intact."""
    findings: list[str] = []
    for relative in REQUIRED_SECURITY_DOCS:
        path = project_root / relative
        if not path.is_file():
            findings.append(f"missing maintained security document: {relative}")
        elif path.stat().st_size == 0:
            findings.append(f"empty maintained security document: {relative}")
    findings.extend(_python_syntax_findings(project_root, REQUIRED_SECURITY_TESTS))
    findings.extend(_python_syntax_findings(project_root, REQUIRED_SECURITY_SCRIPTS))
    return findings


def main() -> int:
    """Run the structural Tier 4 assurance-boundary inventory check."""
    root = Path(__file__).resolve().parents[2]
    findings = verify_security_assurance_boundary(root)
    if findings:
        for finding in findings:
            print(f"FAIL: {finding}")
        return 1
    print("PASS: maintained security-assurance boundary is structurally intact.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
