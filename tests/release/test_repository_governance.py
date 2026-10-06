"""Regression tests for dynamic repository-governance discovery."""

from __future__ import annotations

from typing import Any

from scripts.release import verify_repository_governance as governance


def test_ruleset_uses_runtime_default_branch(monkeypatch) -> None:
    """Branch ruleset matching must use the branch reported by GitHub at runtime."""
    detail: dict[str, Any] = {
        "conditions": {"ref_name": {"include": ["refs/heads/trunk"]}},
        "rules": [
            {"type": "pull_request"},
            {
                "type": "required_status_checks",
                "parameters": {
                    "required_status_checks": [{"context": "release-verification"}]
                },
            },
            {"type": "required_linear_history"},
            {"type": "deletion"},
        ],
    }

    monkeypatch.setattr(governance, "get", lambda _path: (200, detail))
    failures: list[str] = []

    assert governance.verify_default_branch_ruleset(
        [{"id": 7, "target": "branch"}], failures, branch="trunk"
    )
    assert failures == []


def test_legacy_protection_path_uses_runtime_branch_and_url_encoding(
    monkeypatch,
) -> None:
    """Legacy fallback must not assume a literal main-branch path."""
    requested: list[str] = []

    def fake_get(path: str) -> tuple[int, Any]:
        requested.append(path)
        return (
            200,
            {
                "required_status_checks": {"contexts": ["ci"]},
                "enforce_admins": {"enabled": True},
                "required_pull_request_reviews": {},
            },
        )

    monkeypatch.setattr(governance, "get", fake_get)
    failures: list[str] = []

    assert governance.verify_legacy_default_branch_protection(
        failures, branch="release/stable"
    )
    assert requested == ["/branches/release%2Fstable/protection"]
    assert failures == []
