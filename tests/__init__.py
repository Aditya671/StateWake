"""Test package bootstrap for source-checkout imports."""

from __future__ import annotations

import sys

from scripts.common.project_paths import SRC_PATH

SRC = SRC_PATH
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
