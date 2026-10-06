"""Verify that every supported CLI command can be loaded from the built package."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import cast

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from scripts.common.project_metadata import load_project_metadata  # noqa: E402
from scripts.common.project_paths import PROJECT_ROOT  # noqa: E402

METADATA = load_project_metadata(PROJECT_ROOT)
SOURCE_ROOT = PROJECT_ROOT / METADATA.module_root
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))


def _supported_commands() -> Callable[[], Iterable[str]]:
    """Load the command inventory from the configured CLI module."""
    module = importlib.import_module(METADATA.cli_module)
    provider = getattr(module, "supported_commands", None)
    if not callable(provider):
        raise RuntimeError(
            f"configured CLI module {METADATA.cli_module!r} has no supported_commands()"
        )
    return cast(Callable[[], Iterable[str]], provider)


def _commands() -> list[str]:
    """Return the stable list of supported top-level commands."""
    return list(_supported_commands()())


def main() -> None:
    """Run CLI help/version smoke checks for every supported command."""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        filter(None, (str(SOURCE_ROOT), environment.get("PYTHONPATH")))
    )
    subprocess.run(
        [sys.executable, "-m", METADATA.cli_module, "version"],
        check=True,
        env=environment,
    )
    commands = _commands()
    for command in commands:
        subprocess.run(
            [sys.executable, "-m", METADATA.cli_module, command, "--help"],
            check=True,
            env=environment,
        )
    print(f"CLI surface: verified {len(commands)} supported commands")


if __name__ == "__main__":
    main()
