"""Verify Tier 11 identity/access-control assurance structure."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/security/identity_bound_access.md"
MODULE = ROOT / "src/statewake/domain/access_control.py"
TEST = ROOT / "tests/security/test_identity_access_controls.py"

REQUIRED_SYMBOLS = (
    "AuthorizationOperation",
    "PrincipalStatus",
    "Principal",
    "AuthorizationRequest",
    "AuthorizationGrant",
    "AuthorizationDecision",
    "AuthorizationPolicy",
    "authorize",
)
REQUIRED_TEST_NAMES = (
    "test_authenticated_but_unauthorized",
    "test_read_does_not_imply_write",
    "test_wrong_resource_is_denied",
    "test_unauthorized_recovery_is_denied",
    "test_unauthorized_attestation_is_denied",
    "test_invalid_resource_state_is_denied",
    "test_role_confusion_is_denied",
    "test_revoked_principal_is_denied",
    "test_expired_principal_is_denied",
    "test_cross_domain_access_is_denied",
)


def _defined_names(path: Path) -> set[str]:
    """Return class/function names defined in one Python source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }


def main() -> int:
    """Return zero when maintained Tier 11 authorities are structurally complete."""
    failures: list[str] = []
    for label, path in (
        ("documentation", DOC),
        ("implementation", MODULE),
        ("tests", TEST),
    ):
        if not path.is_file():
            failures.append(f"missing {label}: {path}")
    if DOC.is_file() and DOC.stat().st_size == 0:
        failures.append(f"empty documentation: {DOC}")
    if MODULE.is_file():
        names = _defined_names(MODULE)
        failures.extend(
            f"missing implementation symbol: {symbol}"
            for symbol in REQUIRED_SYMBOLS
            if symbol not in names
        )
    if TEST.is_file():
        names = _defined_names(TEST)
        failures.extend(
            f"missing required regression test: {name}"
            for name in REQUIRED_TEST_NAMES
            if name not in names
        )

    print("TIER11_ASSURANCE: " + ("PASS" if not failures else "FAIL"))
    if failures:
        print("\n".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
