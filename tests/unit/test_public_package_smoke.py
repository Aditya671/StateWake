"""Smoke tests for the stabilized public package surface."""

import os
import subprocess
import sys

import statewake
from config.project_paths import SRC_PATH


def test_public_package_version() -> None:
    """Verify the public package imports and exposes its current version."""
    assert statewake.__version__ == "0.3.0"


def test_cli_version_from_source_tree() -> None:
    """Verify the CLI version command loads without hidden legacy imports."""
    environment = os.environ.copy()
    source_root = str(SRC_PATH)
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, (source_root, environment.get("PYTHONPATH")))
    )
    result = subprocess.run(
        [sys.executable, "-m", "statewake.cli.main", "version"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert result.stdout.strip() == statewake.__version__


def test_subpackage_public_import_surfaces() -> None:
    """Verify supported subpackages expose their public import surfaces."""
    from statewake.adapters import JsonlReliabilityStateStore
    from statewake.cli import main
    from statewake.domain import EvidenceItem, ReliabilityStateTransition
    from statewake.services import build_reliability_evidence_chain

    assert JsonlReliabilityStateStore is not None
    assert main is not None
    assert EvidenceItem is not None
    assert ReliabilityStateTransition is not None
    assert build_reliability_evidence_chain is not None
