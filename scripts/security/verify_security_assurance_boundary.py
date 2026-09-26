"""Deterministically verify the Tier 4 security-assurance evidence boundary."""

from __future__ import annotations

import re
from pathlib import Path

REQUIRED_THREAT_IDS = tuple(f"T{i:02d}" for i in range(1, 16))
REQUIRED_SECTIONS = (
    "## Assets and security properties",
    "## Adversaries",
    "## Trust boundaries",
    "## Threat matrix",
    "## Cryptography policy",
    "## Input and resource security",
    "## Privacy model",
    "## Out of scope / not automatically protected",
    "## Residual-risk handling",
)


def verify_security_assurance_boundary(project_root: Path) -> list[str]:
    """Return deterministic Tier 4 assurance findings; an empty list means pass."""
    findings: list[str] = []
    security_dir = project_root / "docs" / "security"
    threat_model = (security_dir / "THREAT_MODEL.md").read_text(encoding="utf-8")
    control_matrix = (security_dir / "CONTROL_TEST_MATRIX.md").read_text(
        encoding="utf-8"
    )
    incident_recovery = (security_dir / "INCIDENT_RECOVERY.md").read_text(
        encoding="utf-8"
    )
    security_adr = (
        project_root / "docs" / "adr" / "0004-security-architecture.md"
    ).read_text(encoding="utf-8")

    findings.extend(
        f"missing threat-model section: {section}"
        for section in REQUIRED_SECTIONS
        if section not in threat_model
    )

    threat_ids = tuple(re.findall(r"\| (T\d{2}) \|", threat_model))
    if threat_ids != REQUIRED_THREAT_IDS:
        findings.append("threat matrix does not contain exactly T01 through T15")

    refs = sorted(set(re.findall(r"`(tests/[^`]+)`", threat_model)))
    if not refs:
        findings.append("threat model has no executable evidence references")
    for reference in refs:
        path_text, _, node = reference.partition("::")
        path = project_root / path_text
        if not path.exists():
            findings.append(f"missing executable evidence: {reference}")
        elif node and node.rsplit("::", 1)[-1] not in path.read_text(encoding="utf-8"):
            findings.append(f"missing executable evidence node: {reference}")

    matrix_refs = sorted(set(re.findall(r"`(tests/[^`]+\.py)`", control_matrix)))
    if not matrix_refs:
        findings.append("control matrix has no executable test references")
    for reference in matrix_refs:
        if not (project_root / reference).exists():
            findings.append(f"missing control-matrix test: {reference}")

    required_recovery_terms = (
        "authoritative",
        "revoke",
        "rotate",
        "independent trust checkpoint",
        "does not manufacture",
    )
    for term in required_recovery_terms:
        if term not in incident_recovery.lower():
            findings.append(f"incident recovery evidence missing: {term}")

    for term in (
        "ReliabilityEvidenceChain",
        "THREAT_MODEL.md",
        "Ed25519",
        "Private signing material remains outside StateWake",
    ):
        if term not in security_adr:
            findings.append(f"security ADR missing bounded claim: {term}")

    return findings


def main() -> int:
    """Run the Tier 4 assurance verifier against the repository root."""
    root = Path(__file__).resolve().parents[2]
    findings = verify_security_assurance_boundary(root)
    if findings:
        for finding in findings:
            print(f"FAIL: {finding}")
        return 1
    print("PASS: Tier 4 security-assurance evidence is internally consistent.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
