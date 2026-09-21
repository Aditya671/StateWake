"""Verify Tier 7 trust-domain and anchor assurance evidence consistency."""

from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REQUIRED_FILES = (
    "docs/security/trust_domain_anchor_assurance.md",
    "src/statewake/domain/trust_anchor.py",
    "src/statewake/adapters/trust_anchor.py",
    "src/statewake/domain/attestation_trust.py",
    "src/statewake/adapters/key_management.py",
    "docs/security/recovery_resilience_assurance.md",
)
REQUIRED_TERMS = (
    "D1",
    "D2",
    "D3",
    "D4",
    "D5",
    "D6",
    "key-purpose separation",
    "independent checkpoint assurance",
    "trust-anchor compromise behavior",
    "historical verification policy",
    "not a release approval",
)
REQUIRED_SYMBOLS = (
    "class TrustCheckpoint",
    "def compare_local_tip",
    "def ensure_checkpoint_sequence",
    "class JsonTrustAnchorStore",
    "class SignedAttestationTrustState",
    "class ExternalSigningAdapter",
)
REQUIRED_TESTS = (
    "test_checkpoint_store_rejects_conflicting_overwrite",
    "test_checkpoint_disagreement_is_security_discrepancy",
    "test_key_purpose_separation_is_explicit",
    "test_attestation_trust_rotation_preserves_history",
    "test_anchor_compromise_never_self_authenticates",
)


@dataclass(frozen=True, slots=True)
class Finding:
    """Represent one deterministic assurance finding."""

    category: str
    detail: str


def verify(root: Path) -> tuple[Finding, ...]:
    """Return deterministic Tier 7 evidence-consistency findings."""
    findings: list[Finding] = []
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            findings.append(Finding("missing-file", relative))

    doc = root / "docs/security/trust_domain_anchor_assurance.md"
    if doc.is_file():
        text = doc.read_text(encoding="utf-8")
        for term in REQUIRED_TERMS:
            if term.lower() not in text.lower():
                findings.append(Finding("missing-semantic-term", term))

    source_map = {
        "src/statewake/domain/trust_anchor.py": REQUIRED_SYMBOLS[:3],
        "src/statewake/adapters/trust_anchor.py": REQUIRED_SYMBOLS[3:4],
        "src/statewake/domain/attestation_trust.py": REQUIRED_SYMBOLS[4:5],
        "src/statewake/adapters/key_management.py": REQUIRED_SYMBOLS[5:6],
    }
    for relative, symbols in source_map.items():
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for symbol in symbols:
            if symbol not in text:
                findings.append(Finding("missing-symbol", symbol))

    tests = root / "tests/security/test_trust_domain_anchors.py"
    if not tests.is_file():
        findings.append(Finding("missing-test-suite", str(tests)))
    else:
        text = tests.read_text(encoding="utf-8")
        for name in REQUIRED_TESTS:
            if f"def {name}" not in text:
                findings.append(Finding("missing-regression", name))

    adapter = root / "src/statewake/adapters/trust_anchor.py"
    if adapter.is_file():
        text = adapter.read_text(encoding="utf-8")
        for term in ("different content", "ensure_checkpoint_sequence"):
            if term not in text:
                findings.append(Finding("missing-anchor-invariant", term))

    attest = root / "src/statewake/domain/attestation_trust.py"
    if attest.is_file():
        text = attest.read_text(encoding="utf-8")
        for term in ("revoked", "superseded", "previous_digest"):
            if term not in text:
                findings.append(Finding("missing-key-lifecycle", term))

    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        import tomllib

        pyproject_text = pyproject.read_text(encoding="utf-8")
        project_version = str(tomllib.loads(pyproject_text)["project"]["version"])
        package_text = (root / "src/statewake/__init__.py").read_text(encoding="utf-8")
        if f'__version__ = "{project_version}"' not in package_text:
            findings.append(
                Finding("release-boundary", "package version is not synchronized")
            )
    return tuple(findings)


def run_tests(root: Path) -> int:
    """Run the Tier 7 focused regression suite."""
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/security/test_trust_domain_anchors.py",
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
    findings = verify(args.root.resolve())
    if findings:
        print("TRUST DOMAIN ASSURANCE: FAIL")
        for item in findings:
            print(f"- [{item.category}] {item.detail}")
        return 1
    print("TRUST DOMAIN ASSURANCE: PASS")
    if args.run_tests:
        return run_tests(args.root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
