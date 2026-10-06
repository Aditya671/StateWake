"""Verify StateWake release-input manifest and candidate fingerprint."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from scripts.common.project_paths import PROJECT_ROOT  # noqa: E402
from scripts.common.release_identity import (  # noqa: E402
    read_manifest,
    source_tree_digest,
    validate_release_identity,
)


def main() -> int:
    """Validate release identity without rewriting any source-tree artifact."""
    validate_release_identity(PROJECT_ROOT)
    print(
        json.dumps(
            {
                "status": "verified",
                "manifest_records": len(read_manifest(PROJECT_ROOT)),
                "source_tree_sha256": source_tree_digest(PROJECT_ROOT),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
