#!/usr/bin/env python3
"""Verify that Tier 12 containment evidence is present and internally consistent."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/security/runtime_containment.md"
MODULE = ROOT / "src/statewake/domain/runtime_containment.py"
SERVER = ROOT / "src/statewake/server.py"
OPERATIONS = ROOT / "src/statewake/services/operations_service.py"
PORTABLE = ROOT / "scripts/security/verify_reliability_proof_portability.py"
TESTS = ROOT / "tests/security/test_runtime_containment.py"

REQUIRED_DOC_PHRASES = (
    "maximum input bytes",
    "maximum archive members",
    "maximum JSON nesting depth",
    "maximum JSON node count",
    "maximum cooperative verification time",
    "external-reference scheme validation",
    "Archive contents are data only",
    "no unnecessary network egress",
    "dedicated temporary root",
    "not a release",
)

REQUIRED_SYMBOLS = (
    "ContainmentViolation",
    "RuntimeContainmentLimits",
    "VerificationDeadline",
    "load_bounded_json",
    "validate_archive_envelope",
    "validate_archive_metadata",
    "validate_input_size",
    "validate_reference",
)

REQUIRED_TESTS = (
    "test_rejects_oversized_input",
    "test_rejects_deep_json",
    "test_rejects_excessive_json_nodes",
    "test_rejects_oversized_string",
    "test_rejects_archive_ratio",
    "test_rejects_archive_expansion",
    "test_rejects_archive_traversal",
    "test_rejects_archive_symlink",
    "test_rejects_external_reference",
    "test_deadline_is_bounded",
    "test_server_uses_bounded_json_loader",
    "test_archive_verification_does_not_execute_members",
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One deterministic Tier 12 evidence finding."""

    kind: str
    detail: str


def _functions(path: Path) -> set[str]:
    """Return top-level and class method names present in one Python file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return names


def verify() -> list[Finding]:
    """Return all missing Tier 12 evidence items."""
    findings: list[Finding] = []
    if not DOC.is_file():
        return [Finding("missing-document", str(DOC))]
    document = DOC.read_text(encoding="utf-8")
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in document:
            findings.append(Finding("missing-document-evidence", phrase))

    if not MODULE.is_file():
        findings.append(Finding("missing-module", str(MODULE)))
    else:
        names = _functions(MODULE)
        classes = {
            node.name
            for node in ast.walk(ast.parse(MODULE.read_text(encoding="utf-8")))
            if isinstance(node, ast.ClassDef)
        }
        for symbol in REQUIRED_SYMBOLS:
            if symbol not in names and symbol not in classes:
                findings.append(Finding("missing-symbol", symbol))

    server_text = SERVER.read_text(encoding="utf-8") if SERVER.is_file() else ""
    operations_text = (
        OPERATIONS.read_text(encoding="utf-8") if OPERATIONS.is_file() else ""
    )
    portable_text = PORTABLE.read_text(encoding="utf-8") if PORTABLE.is_file() else ""
    checks = {
        "server-bounded-json": "load_bounded_json" in server_text
        and "runtime_limits" in server_text,
        "operations-archive-preflight": "validate_archive_envelope" in operations_text,
        "portable-json-bound": "MAX_JSON_DEPTH" in portable_text
        and "MAX_ARCHIVE_COMPRESSION_RATIO" in portable_text,
        "portable-size-bound": "MAX_INPUT_BYTES" in portable_text,
    }
    findings.extend(
        Finding("missing-integration", name)
        for name, present in checks.items()
        if not present
    )

    if not TESTS.is_file():
        findings.append(Finding("missing-regression-suite", str(TESTS)))
    else:
        tests = _functions(TESTS)
        for test in REQUIRED_TESTS:
            if test not in tests:
                findings.append(Finding("missing-regression", test))
    return findings


def main() -> int:
    """Print the deterministic Tier 12 result and return a shell status."""
    findings = verify()
    if findings:
        print("TIER12_CONTAINMENT: FAIL")
        for finding in findings:
            print(f"- [{finding.kind}] {finding.detail}")
        return 1
    print("TIER12_CONTAINMENT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
