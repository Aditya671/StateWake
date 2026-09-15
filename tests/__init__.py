"""Test package bootstrap for direct unittest discovery."""

from __future__ import annotations

import sys

from config.project_paths import SRC_PATH

SRC = SRC_PATH
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
