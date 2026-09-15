"""Define canonical environment roots for local and deployment workflows."""

from __future__ import annotations

import os
from pathlib import Path

from config.project_paths import DATA_PATH

ENVIRONMENTS_PATH: Path = DATA_PATH / "environments"
LOCAL: Path = ENVIRONMENTS_PATH / "local"
DEV: Path = ENVIRONMENTS_PATH / "dev"
STAGE: Path = ENVIRONMENTS_PATH / "stage"
PROD: Path = ENVIRONMENTS_PATH / "prod"

ENVIRONMENT_PATHS: dict[str, Path] = {
    "local": LOCAL,
    "dev": DEV,
    "stage": STAGE,
    "prod": PROD,
}
CURRENT_ENVIRONMENT: str = os.environ.get("STATEWAKE_ENV", "local").strip().lower()
if CURRENT_ENVIRONMENT not in ENVIRONMENT_PATHS:
    raise ValueError(
        f"Unsupported STATEWAKE_ENV={CURRENT_ENVIRONMENT!r}; "
        f"expected one of {tuple(ENVIRONMENT_PATHS)}"
    )
CURRENT_ENVIRONMENT_PATH: Path = ENVIRONMENT_PATHS[CURRENT_ENVIRONMENT]
