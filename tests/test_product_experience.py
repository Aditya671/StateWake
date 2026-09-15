"""Tests for the public product-experience verification gate."""

from __future__ import annotations

import importlib.util

from config.project_paths import PROJECT_ROOT

ROOT = PROJECT_ROOT
SCRIPT = ROOT / "scripts" / "release" / "verify_product_experience.py"


spec = importlib.util.spec_from_file_location("verify_product_experience", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_required_product_documentation_exists_and_links_resolve() -> None:
    """Require the documented public product experience to be internally linked."""
    assert module.verify_documentation() == []


def test_first_evidence_example_is_executable() -> None:
    """Require the five-minute tutorial to prove verification and tamper rejection."""
    elapsed, output = module.run_example(
        ROOT / "docs" / "examples" / "first-evidence-chain.py"
    )
    assert elapsed >= 0
    assert "verification: PASS" in output
    assert "deliberate tampering: REJECTED" in output
