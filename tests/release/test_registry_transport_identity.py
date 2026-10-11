"""Registry transport identity regressions for release read-back."""

from __future__ import annotations

import statewake
from statewake.release_trust import registry as registry_module


def test_registry_request_reports_current_package_version() -> None:
    """Registry requests must not retain a stale release-line User-Agent."""
    request = registry_module._registry_request(
        "https://pypi.org/pypi/statewake-ai/0.5.1/json"
    )
    assert request.get_header("User-agent") == f"StateWake/{statewake.__version__}"
    assert request.get_header("Accept") == "application/json"
