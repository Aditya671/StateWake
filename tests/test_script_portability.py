"""Verify validation scripts resolve the package independently of caller cwd."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from config.project_paths import PROJECT_ROOT

ROOT = PROJECT_ROOT
SCRIPTS = (
    Path("testing/failure_lab.py"),
    Path("testing/property_state_machine.py"),
    Path("integration/run_external_integrations.py"),
)


def test_cli_scripts_are_invocable_from_outside_repository() -> None:
    """Ensure argparse-based scripts can start from an unrelated cwd."""
    with TemporaryDirectory() as temporary_directory:
        for name in SCRIPTS:
            environment = os.environ.copy()
            python_path = os.pathsep.join(
                (str(ROOT), str(ROOT / "src"), environment.get("PYTHONPATH", ""))
            )
            environment["PYTHONPATH"] = python_path
            completed = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / name), "--help"],
                cwd=temporary_directory,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert completed.returncode == 0, (
                name,
                completed.stdout,
                completed.stderr,
            )
