#!/usr/bin/env python3
"""Verify Tier 13 data-lifecycle and confidentiality evidence."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/security/data_lifecycle_confidentiality.md"
MODULE = ROOT / "src/statewake/domain/data_lifecycle.py"
OPERATIONS = ROOT / "src/statewake/domain/operations.py"
TELEMETRY = ROOT / "src/statewake/adapters/opentelemetry.py"
SERVER = ROOT / "src/statewake/server.py"
TESTS = ROOT / "tests/security/test_data_lifecycle_confidentiality.py"

REQUIRED_DOC_PHRASES = (
    "Data Lifecycle & Confidentiality Protection",
    "classification inheritance",
    "retention",
    "payload deletion",
    "historical claim preservation",
    "minimal disclosure",
    "encryption at rest",
    "TLS",
    "sensitive errors",
    "not a release",
)
REQUIRED_SYMBOLS = (
    "DataLifecyclePolicy",
    "DataLifecycleDecision",
    "DeletionRecord",
    "inherit_sensitivity",
    "assess_data_lifecycle",
    "build_deletion_record",
    "filter_disclosable_ids",
)
REQUIRED_TESTS = (
    "test_derived_sensitivity_cannot_downgrade_without_approval",
    "test_lifecycle_retention_and_legal_hold",
    "test_deletion_record_preserves_history_without_payload",
    "test_disclosure_ceiling_blocks_sensitive_objects",
    "test_encryption_and_tls_requirements_are_explicit",
    "test_telemetry_does_not_expose_restricted_evidence",
    "test_http_errors_do_not_echo_untrusted_payload",
    "test_operational_bundle_rejects_sensitivity_downgrade",
    "test_disclosed_bundle_excludes_restricted_artifacts",
    "test_content_store_deletion_requires_expired_retention",
    "test_cross_resource_confidentiality_isolation_delegates_to_authorization",
)


@dataclass(frozen=True, slots=True)
class Finding:
    """One deterministic Tier 13 evidence finding."""

    kind: str
    detail: str


def _names(path: Path) -> set[str]:
    """Return function and class names defined by one Python module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def verify() -> list[Finding]:
    """Return missing Tier 13 evidence items."""
    findings: list[Finding] = []
    if not DOC.is_file():
        return [Finding("missing-document", str(DOC))]
    document = DOC.read_text(encoding="utf-8").casefold()
    findings.extend(
        Finding("missing-document-evidence", phrase)
        for phrase in REQUIRED_DOC_PHRASES
        if phrase.casefold() not in document
    )
    if not MODULE.is_file():
        findings.append(Finding("missing-module", str(MODULE)))
    else:
        names = _names(MODULE)
        findings.extend(
            Finding("missing-symbol", symbol)
            for symbol in REQUIRED_SYMBOLS
            if symbol not in names
        )
    operations = OPERATIONS.read_text(encoding="utf-8")
    telemetry = TELEMETRY.read_text(encoding="utf-8")
    server = SERVER.read_text(encoding="utf-8")
    integration_checks = {
        "operational-classification-inheritance": "inherit_sensitivity" in operations,
        "telemetry-redaction": "Redactor" in telemetry
        and "privacy_policy" in telemetry,
        "generic-http-error": '"INVALID_REQUEST"' in server
        and "verification request is invalid" in server,
    }
    findings.extend(
        Finding("missing-integration", name)
        for name, present in integration_checks.items()
        if not present
    )
    if not TESTS.is_file():
        findings.append(Finding("missing-regression-suite", str(TESTS)))
    else:
        test_names = _names(TESTS)
        findings.extend(
            Finding("missing-regression", test)
            for test in REQUIRED_TESTS
            if test not in test_names
        )
    return findings


def main() -> int:
    """Print the deterministic Tier 13 result and return a shell status."""
    findings = verify()
    if findings:
        print("TIER13_DATA_LIFECYCLE: FAIL")
        for finding in findings:
            print(f"- [{finding.kind}] {finding.detail}")
        return 1
    print("TIER13_DATA_LIFECYCLE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
