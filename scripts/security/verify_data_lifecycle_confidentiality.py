"""Verify Tier 13 data-lifecycle/confidentiality assurance structure."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/security/data_lifecycle_confidentiality.md"
MODULE = ROOT / "src/statewake/domain/data_lifecycle.py"
OPERATIONS = ROOT / "src/statewake/domain/operations.py"
TELEMETRY = ROOT / "src/statewake/adapters/opentelemetry.py"
INGESTION = ROOT / "src/statewake/adapters/evidence_ingestion.py"
PRIVACY_RUNTIME = ROOT / "src/statewake/services/privacy_governance_runtime_service.py"
SERVER = ROOT / "src/statewake/server.py"
TESTS = ROOT / "tests/security/test_data_lifecycle_confidentiality.py"

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
    "test_runtime_governance_omits_restricted_evidence_ids_from_telemetry",
    "test_runtime_governance_rejects_storage_before_artifact_write",
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


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _defined_names(path: Path) -> set[str]:
    return {
        node.name
        for node in ast.walk(_tree(path))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def _identifiers(path: Path) -> set[str]:
    names = _defined_names(path)
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def verify() -> list[Finding]:
    """Return missing Tier 13 structural evidence items."""
    findings: list[Finding] = []
    if not DOC.is_file():
        findings.append(Finding("missing-document", str(DOC)))
    elif DOC.stat().st_size == 0:
        findings.append(Finding("empty-document", str(DOC)))

    for path in (
        MODULE,
        OPERATIONS,
        TELEMETRY,
        INGESTION,
        PRIVACY_RUNTIME,
        SERVER,
        TESTS,
    ):
        if not path.is_file():
            findings.append(Finding("missing-file", str(path)))
    if findings:
        return findings

    names = _defined_names(MODULE)
    findings.extend(
        Finding("missing-symbol", symbol)
        for symbol in REQUIRED_SYMBOLS
        if symbol not in names
    )

    integration_requirements = {
        "operational-classification-inheritance": (OPERATIONS, {"inherit_sensitivity"}),
        "telemetry-redaction": (TELEMETRY, {"Redactor", "privacy_policy"}),
        "prewrite-evidence-governance": (
            INGESTION,
            {"evaluate_evidence_governance", "storage_allowed", "put"},
        ),
        "telemetry-evidence-projection": (
            TELEMETRY,
            {"project_manifest_for_telemetry", "privacy_governance"},
        ),
        "runtime-policy-evidence": (
            PRIVACY_RUNTIME,
            {
                "write_privacy_governance_runtime_snapshot",
                "load_privacy_governance_runtime_snapshot",
            },
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
