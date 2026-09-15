"""Define canonical repository paths independently of the caller's working directory."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
CONFIG_PATH: Path = PROJECT_ROOT / "config"
DOCS_PATH: Path = PROJECT_ROOT / "docs"
SCRIPTS_PATH: Path = PROJECT_ROOT / "scripts"
SRC_PATH: Path = PROJECT_ROOT / "src"
TESTS_PATH: Path = PROJECT_ROOT / "tests"
DATA_PATH: Path = PROJECT_ROOT / "data"
DIST_PATH: Path = PROJECT_ROOT / "dist"
VERIFICATION_PATH: Path = PROJECT_ROOT / "verification"
