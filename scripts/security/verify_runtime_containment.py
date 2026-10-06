"""Verify Tier 12 runtime-containment assurance structure."""

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

REQUIRED_SYMBOLS = (
    "ContainmentViolationError",
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
    "test_archive_verification_does_not_execute_members",
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One deterministic Tier 12 evidence finding."""

    kind: str
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
    """Return identifiers/attribute names referenced by one Python source file."""
    names: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def verify() -> list[Finding]:
    """Return missing Tier 12 structural evidence items."""
    findings: list[Finding] = []
    if not DOC.is_file():
        findings.append(Finding("missing-document", str(DOC)))
    elif DOC.stat().st_size == 0:
        findings.append(Finding("empty-document", str(DOC)))

    for path in (MODULE, SERVER, OPERATIONS, PORTABLE, TESTS):
        if not path.is_file():
            findings.append(Finding("missing-file", str(path)))
    if findings:
        return findings

    module_names = _defined_names(MODULE)
    findings.extend(
        Finding("missing-symbol", symbol)
        for symbol in REQUIRED_SYMBOLS
        if symbol not in module_names
    )

    integration_requirements = {
        "server-bounded-json": (SERVER, {"load_bounded_json", "runtime_limits"}),
        "operations-archive-preflight": (OPERATIONS, {"validate_archive_envelope"}),
        "portable-json-bounds": (
            PORTABLE,
            {"MAX_JSON_DEPTH", "MAX_ARCHIVE_COMPRESSION_RATIO", "MAX_INPUT_BYTES"},
        ),
    }
    for label, (path, required) in integration_requirements.items():
        if not required <= _identifiers(path):
            findings.append(Finding("missing-integration", label))

    test_names = _defined_names(TESTS)
    findings.extend(
        Finding("missing-regression", test)
        for test in REQUIRED_TESTS
        if test not in test_names
    )
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
