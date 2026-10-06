"""Golden Application C: synthetic municipal decision reliability integration."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from examples.golden.runtime import print_result, run_municipal  # noqa: E402

if __name__ == "__main__":
    print_result(run_municipal())
