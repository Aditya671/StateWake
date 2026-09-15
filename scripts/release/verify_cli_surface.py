"""Verify that every supported CLI command can be loaded from the built package."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from config.project_paths import SRC_PATH  # noqa: E402

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from statewake.cli.main import supported_commands  # noqa: E402

SOURCE_ROOT = SRC_PATH
sys.path.insert(0, str(SOURCE_ROOT))


def _commands() -> list[str]:
    """Return the stable list of supported top-level commands."""
    return list(supported_commands())


def main() -> None:
    """Run CLI help/version smoke checks for every supported command."""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(SOURCE_ROOT), environment.get("PYTHONPATH")))
    )
    subprocess.run(
        [sys.executable, "-m", "statewake.cli.main", "version"],
        check=True,
        env=environment,
    )
    commands = _commands()
    for command in commands:
        subprocess.run(
            [sys.executable, "-m", "statewake.cli.main", command, "--help"],
            check=True,
            env=environment,
        )
    print(f"CLI surface: verified {len(commands)} supported commands")


if __name__ == "__main__":
    main()
