"""Verify Tier 11 authorization-assurance documentation and implementation evidence."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/security/identity_bound_access.md"
MODULE = ROOT / "src/statewake/domain/access_control.py"
TEST = ROOT / "tests/security/test_identity_access_controls.py"

REQUIRED_DOC_MARKERS = (
    "Identity-Bound Access & Least Privilege",
    "development assurance",
    "principal → operation → resource domain → resource → resource state → decision",
    "Identity-provider implementation remains outside StateWake.",
    "Authorization uncertainty is never interpreted as permission.",
)
REQUIRED_SYMBOLS = (
    "class AuthorizationOperation",
    "class PrincipalStatus",
    "class Principal",
    "class AuthorizationRequest",
    "class AuthorizationGrant",
    "class AuthorizationDecision",
    "class AuthorizationPolicy",
    "def authorize(",
)
REQUIRED_TEST_NAMES = (
    "authenticated_but_unauthorized",
    "read_does_not_imply_write",
    "wrong_resource_is_denied",
    "unauthorized_recovery_is_denied",
    "unauthorized_attestation_is_denied",
    "invalid_resource_state_is_denied",
    "role_confusion_is_denied",
    "revoked_principal_is_denied",
    "expired_principal_is_denied",
    "cross_domain_access_is_denied",
)


def main() -> int:
    """Return zero only when the Tier 11 assurance evidence is structurally complete."""
    failures: list[str] = []
    if not DOC.is_file():
        failures.append(f"missing documentation: {DOC}")
    if not MODULE.is_file():
        failures.append(f"missing implementation: {MODULE}")
    if not TEST.is_file():
        failures.append(f"missing tests: {TEST}")
    if failures:
        print("TIER11_ASSURANCE: FAIL")
        print("\n".join(failures))
        return 1

    doc_text = DOC.read_text(encoding="utf-8")
    module_text = MODULE.read_text(encoding="utf-8")
    test_text = TEST.read_text(encoding="utf-8")
    failures.extend(
        f"missing documentation marker: {marker}"
        for marker in REQUIRED_DOC_MARKERS
        if marker not in doc_text
    )
    failures.extend(
        f"missing implementation symbol: {symbol}"
        for symbol in REQUIRED_SYMBOLS
        if symbol not in module_text
    )
    failures.extend(
        f"missing required regression test: {name}"
        for name in REQUIRED_TEST_NAMES
        if name not in test_text
    )

    print("TIER11_ASSURANCE: " + ("PASS" if not failures else "FAIL"))
    if failures:
        print("\n".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
