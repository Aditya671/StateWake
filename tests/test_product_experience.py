"""Tests for the public product-experience verification gate."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from tempfile import TemporaryDirectory

from scripts.common.project_paths import EXAMPLES_PATH, PROJECT_ROOT

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
    elapsed, output = module.run_example(EXAMPLES_PATH / "first-evidence-chain.py")
    assert elapsed >= 0
    assert "verification: PASS" in output
    assert "deliberate tampering: REJECTED" in output


def test_public_examples_bootstrap_without_repository_pythonpath() -> None:
    """Public examples must run without caller cwd or PYTHONPATH assumptions."""
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    with TemporaryDirectory() as temporary_directory:
        for example in module.EXAMPLES:
            completed = subprocess.run(
                [sys.executable, str(example)],
                cwd=temporary_directory,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert completed.returncode == 0, (
                example.relative_to(ROOT),
                completed.stdout,
                completed.stderr,
            )
