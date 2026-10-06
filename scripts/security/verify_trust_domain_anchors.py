"""Verify Tier 7 trust-domain and anchor assurance structure."""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REQUIRED_DOCUMENTS = (
    "docs/security/trust_domain_anchor_assurance.md",
    "docs/security/recovery_resilience_assurance.md",
)
REQUIRED_SOURCE_SYMBOLS = {
    "src/statewake/domain/trust_anchor.py": {
        "TrustCheckpoint",
        "compare_local_tip",
        "ensure_checkpoint_sequence",
    },
    "src/statewake/adapters/trust_anchor.py": {"JsonTrustAnchorStore"},
    "src/statewake/domain/attestation_trust.py": {
        "AttestationTrustAnchor",
        "SignedAttestationTrustState",
        "validate_attestation_trust_transition",
    },
    "src/statewake/adapters/key_management.py": {
        "ExternalSigningAdapter",
        "ExternalCommandSigningProvider",
    },
    "src/statewake/services/reliability_attestation_service.py": {
        "resolve_reliability_attestation_trust_state",
        "verify_persisted_signed_reliability_outcome",
    },
}
REQUIRED_TESTS = (
    "test_checkpoint_store_rejects_conflicting_overwrite",
    "test_checkpoint_disagreement_is_security_discrepancy",
    "test_attestation_trust_rotation_preserves_history",
)


@dataclass(frozen=True, slots=True)
class Finding:
    """Represent one deterministic assurance finding."""

    category: str
    detail: str


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _defined_names(path: Path) -> set[str]:
    return {
        node.name
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def _identifiers(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def verify(root: Path) -> tuple[Finding, ...]:
    """Return structural Tier 7 assurance findings.

    Documentation is required as operator guidance, but assurance is derived from
    executable symbols and behavioral regressions rather than prose snippets.
    """
    findings: list[Finding] = []
    for relative in REQUIRED_DOCUMENTS:
        path = root / relative
        if not path.is_file():
            findings.append(Finding("missing-document", relative))
        elif path.stat().st_size == 0:
            findings.append(Finding("empty-document", relative))

    for relative, required in REQUIRED_SOURCE_SYMBOLS.items():
        path = root / relative
        if not path.is_file():
            findings.append(Finding("missing-source", relative))
            continue
        names = _defined_names(path)
        findings.extend(
            Finding("missing-symbol", f"{relative}:{symbol}")
            for symbol in sorted(required - names)
        )

    tests = root / "tests/security/test_trust_domain_anchors.py"
    if not tests.is_file():
        findings.append(Finding("missing-test-suite", str(tests)))
    else:
        test_names = _defined_names(tests)
        findings.extend(
            Finding("missing-regression", name)
            for name in REQUIRED_TESTS
            if name not in test_names
        )

    adapter = root / "src/statewake/adapters/trust_anchor.py"
    if adapter.is_file() and "ensure_checkpoint_sequence" not in _identifiers(adapter):
        findings.append(
            Finding("missing-anchor-invariant", "ensure_checkpoint_sequence")
        )

    trust = root / "src/statewake/domain/attestation_trust.py"
    if trust.is_file():
        identifiers = _identifiers(trust)
        for field in ("status", "superseded_by", "previous_digest"):
            if field not in identifiers:
                findings.append(Finding("missing-key-lifecycle", field))

    return tuple(findings)


def run_tests(root: Path) -> int:
    """Run the Tier 7 focused behavioral regression suite."""
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/security/test_trust_domain_anchors.py",
            "tests/test_key_management.py",
            "tests/test_signed_attestation_persistence.py",
            "-q",
        ],
        cwd=root,
        check=False,
    )
    return completed.returncode


def main() -> int:
    """Run the Tier 7 evidence verifier."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--run-tests", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    findings = verify(root)
    if findings:
        print("TRUST DOMAIN ASSURANCE: FAIL")
        for item in findings:
            print(f"- [{item.category}] {item.detail}")
        return 1
    print("TRUST DOMAIN ASSURANCE: PASS")
    if args.run_tests:
        return run_tests(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
