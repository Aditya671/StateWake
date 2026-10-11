"""Verify GitHub repository governance controls required before publication.

This verifier treats GitHub repository rulesets as the canonical governance
mechanism. Legacy branch-protection APIs are used only as a fallback when no
applicable branch ruleset exists.

The script is intentionally read-only. Set ``STATEWAKE_GOVERNANCE_TOKEN`` to a
fine-grained token that can read repository administration settings. For
local/manual runs, ``GITHUB_TOKEN`` is accepted as a fallback.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypeGuard

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from scripts.common.project_metadata import load_project_metadata  # noqa: E402
from scripts.common.project_paths import PROJECT_ROOT  # noqa: E402

METADATA = load_project_metadata(PROJECT_ROOT)
OWNER, REPO = METADATA.github_repository
API = f"https://api.github.com/repos/{OWNER}/{REPO}"
RELEASE_TAG_PATTERN = "refs/tags/v*"
REQUIRED_DEFAULT_BRANCH_STATUS_CHECKS = frozenset(
    {"quality", "tests-linux", "portability-windows", "package"}
)


def get(path: str) -> tuple[int, Any]:
    """Read a governance resource from the repository configuration."""
    token = os.environ.get("STATEWAKE_GOVERNANCE_TOKEN") or os.environ.get(
        "GITHUB_TOKEN"
    )
    if not token:
        raise RuntimeError(
            "STATEWAKE_GOVERNANCE_TOKEN (or GITHUB_TOKEN for local runs) is required "
            "to verify repository governance"
        )
    request = urllib.request.Request(
        API + path,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "statewake-repository-governance-check",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {exc.code} for {path}: {body[:500]}") from exc


def is_mapping(value: object) -> TypeGuard[Mapping[str, Any]]:
    """Return whether a value is a JSON object."""
    return isinstance(value, Mapping)


def active_rulesets(rulesets: object) -> list[dict[str, Any]]:
    """Return active repository ruleset summaries."""
    if not isinstance(rulesets, list):
        return []
    return [
        item
        for item in rulesets
        if isinstance(item, dict) and item.get("enforcement") == "active"
    ]


def ruleset_targets(ruleset: Mapping[str, Any], pattern: str) -> bool:
    """Return whether a ruleset explicitly includes the requested ref pattern."""
    conditions = ruleset.get("conditions")
    if not isinstance(conditions, Mapping):
        return False
    ref_name = conditions.get("ref_name")
    if not isinstance(ref_name, Mapping):
        return False
    include = ref_name.get("include")
    return (
        isinstance(include, Sequence)
        and not isinstance(include, (str, bytes))
        and pattern in include
    )


def ruleset_has_rule(ruleset: Mapping[str, Any], rule_type: str) -> bool:
    """Return whether a ruleset contains the requested rule type."""
    rules = ruleset.get("rules")
    if not isinstance(rules, list):
        return False
    return any(
        isinstance(rule, Mapping) and rule.get("type") == rule_type for rule in rules
    )


def _status_check_contexts(checks: object) -> set[str]:
    """Return normalized required-check contexts from GitHub API payloads."""
    if not isinstance(checks, Sequence) or isinstance(checks, (str, bytes)):
        return set()
    contexts: set[str] = set()
    for check in checks:
        if isinstance(check, str):
            contexts.add(check)
            continue
        if isinstance(check, Mapping):
            context = check.get("context")
            if isinstance(context, str) and context:
                contexts.add(context)
    return contexts


def ruleset_required_status_checks(ruleset: Mapping[str, Any]) -> set[str]:
    """Return configured status-check contexts from a repository ruleset."""
    rules = ruleset.get("rules")
    if not isinstance(rules, list):
        return set()
    for rule in rules:
        if (
            not isinstance(rule, Mapping)
            or rule.get("type") != "required_status_checks"
        ):
            continue
        parameters = rule.get("parameters")
        if not isinstance(parameters, Mapping):
            return set()
        return _status_check_contexts(parameters.get("required_status_checks"))
    return set()


def verify_default_branch_ruleset(
    active: list[dict[str, Any]],
    failures: list[str],
    *,
    branch: str,
) -> bool:
    """Verify the active ruleset protecting the repository default branch."""
    branch_pattern = f"refs/heads/{branch}"
    summaries = [r for r in active if r.get("target") == "branch"]
    for summary in summaries:
        try:
            _, detail = get(f"/rulesets/{summary['id']}")
        except (RuntimeError, KeyError) as exc:
            failures.append(f"cannot verify {branch} branch ruleset: {exc}")
            continue
        if not isinstance(detail, Mapping) or not ruleset_targets(
            detail, branch_pattern
        ):
            continue
        if not ruleset_has_rule(detail, "pull_request"):
            failures.append(f"{branch} ruleset does not require pull-request review")
        configured_checks = ruleset_required_status_checks(detail)
        missing_checks = sorted(
            REQUIRED_DEFAULT_BRANCH_STATUS_CHECKS - configured_checks
        )
        if missing_checks:
            failures.append(
                f"{branch} ruleset is missing required status checks: "
                + ", ".join(missing_checks)
            )
        if not ruleset_has_rule(detail, "required_linear_history"):
            failures.append(f"{branch} ruleset does not require linear history")
        if not ruleset_has_rule(detail, "deletion"):
            failures.append(f"{branch} ruleset does not protect against deletion")
        return True
    return False


def verify_tag_ruleset(active: list[dict[str, Any]], failures: list[str]) -> bool:
    """Verify the active ruleset protecting release tags."""
    summaries = [r for r in active if r.get("target") == "tag"]
    for summary in summaries:
        try:
            _, detail = get(f"/rulesets/{summary['id']}")
        except (RuntimeError, KeyError) as exc:
            failures.append(f"cannot verify release-tag ruleset: {exc}")
            continue
        if not isinstance(detail, Mapping) or not ruleset_targets(
            detail, RELEASE_TAG_PATTERN
        ):
            continue
        if not ruleset_has_rule(detail, "deletion"):
            failures.append("release-tag ruleset does not protect against deletion")
        if not ruleset_has_rule(detail, "non_fast_forward"):
            failures.append(
                "release-tag ruleset does not protect against non-fast-forward updates"
            )
        return True
    return False


def verify_legacy_default_branch_protection(
    failures: list[str], *, branch: str
) -> bool:
    """Verify legacy branch protection when no default-branch ruleset applies."""
    encoded_branch = urllib.parse.quote(branch, safe="")
    try:
        _, protection = get(f"/branches/{encoded_branch}/protection")
    except RuntimeError as exc:
        if "GitHub API 404" in str(exc) and "Branch not protected" in str(exc):
            return False
        failures.append(f"cannot verify {branch} branch protection: {exc}")
        return False
    if not isinstance(protection, Mapping):
        failures.append(f"{branch} branch protection response is invalid")
        return False
    required = protection.get("required_status_checks")
    configured_checks: set[str] = set()
    if isinstance(required, Mapping):
        configured_checks |= _status_check_contexts(required.get("contexts"))
        configured_checks |= _status_check_contexts(required.get("checks"))
    missing_checks = sorted(REQUIRED_DEFAULT_BRANCH_STATUS_CHECKS - configured_checks)
    if missing_checks:
        failures.append(
            f"{branch} branch protection is missing required status checks: "
            + ", ".join(missing_checks)
        )
    enforce_admins = protection.get("enforce_admins")
    if not isinstance(enforce_admins, Mapping) or not enforce_admins.get(
        "enabled", False
    ):
        failures.append(f"{branch} does not enforce protection for administrators")
    if protection.get("required_pull_request_reviews") is None:
        failures.append(f"{branch} does not require pull-request review")
    return True


def main() -> int:
    """Verify the configured repository governance controls."""
    failures: list[str] = []

    _, repo = get("")
    if not isinstance(repo, Mapping):
        failures.append("repository metadata response is invalid")
        default_branch = ""
    else:
        default_branch_value = repo.get("default_branch")
        default_branch = (
            default_branch_value if isinstance(default_branch_value, str) else ""
        )
        if not default_branch:
            failures.append("repository default branch is missing")

    try:
        _, ruleset_response = get("/rulesets")
    except RuntimeError as exc:
        ruleset_response = None
        failures.append(f"cannot verify repository rulesets: {exc}")

    if isinstance(ruleset_response, list) and default_branch:
        active = active_rulesets(ruleset_response)
        branch_protected = verify_default_branch_ruleset(
            active, failures, branch=default_branch
        )
        if not branch_protected:
            branch_protected = verify_legacy_default_branch_protection(
                failures, branch=default_branch
            )
        if not branch_protected:
            failures.append(
                "no active repository ruleset or legacy branch protection protects "
                f"the default branch {default_branch!r}"
            )

        tag_protected = verify_tag_ruleset(active, failures)
        if not tag_protected:
            failures.append("no active repository ruleset protects release tags")

    try:
        _, private_reporting = get("/private-vulnerability-reporting")
        if not isinstance(private_reporting, Mapping) or not private_reporting.get(
            "enabled", False
        ):
            failures.append("GitHub private vulnerability reporting is disabled")
    except RuntimeError as exc:
        failures.append(f"cannot verify private vulnerability reporting: {exc}")

    if failures:
        print("REPOSITORY GOVERNANCE: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("REPOSITORY GOVERNANCE: PASS")
    print(f"- default branch governance verified ({default_branch})")
    print("- release-tag protection verified")
    print("- private vulnerability reporting verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
