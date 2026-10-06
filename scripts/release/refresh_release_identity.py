"""Regenerate StateWake release-input manifest and candidate fingerprint."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from scripts.common.project_paths import PROJECT_ROOT  # noqa: E402
from scripts.common.release_identity import refresh_release_identity  # noqa: E402


def main() -> int:
    """Refresh deterministic release identity for the current repository tree."""
    result = refresh_release_identity(PROJECT_ROOT)
    print(json.dumps({"status": "refreshed", **result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
