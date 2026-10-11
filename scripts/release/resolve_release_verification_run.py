"""Resolve one authoritative successful Release Verification GitHub Actions run."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import cast

API_VERSION = "2022-11-28"
SHA256_RE = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
DEFAULT_WORKFLOW_PATH = ".github/workflows/release-verification.yml"


def _monotonic() -> float:
    """Return the monotonic clock used by bounded polling."""
    return time.monotonic()


def _sleep(seconds: float) -> None:
    """Sleep between bounded GitHub API polls."""
    time.sleep(seconds)


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be an object")
    return cast(Mapping[str, object], value)


def _string(record: Mapping[str, object], field: str) -> str:
    value = record.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"workflow run {field} is missing")
    return value.strip()


def _integer(record: Mapping[str, object], field: str) -> int:
    value = record.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"workflow run {field} is invalid")
    return value


def _token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required to resolve Release Verification")
    return token


def _validate_repository(repository: str) -> str:
    if not REPOSITORY_RE.fullmatch(repository):
        raise ValueError("repository must use owner/name form")
    return repository


def _validate_sha(value: str, field: str) -> str:
    normalized = value.strip().lower()
    if not SHA256_RE.fullmatch(normalized):
        raise ValueError(f"{field} must be a 40-character lowercase Git SHA")
    return normalized


def _api_json(repository: str, path: str, *, token: str) -> object:
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repository}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "statewake-release-verification-resolver",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API {exc.code} while resolving Release Verification: {body[:500]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise ConnectionError(
            f"GitHub API transport failure while resolving Release Verification: {exc.reason}"
        ) from exc


def _validated_run(
    raw: object,
    *,
    workflow_path: str,
    expected_source_revision: str | None,
) -> dict[str, object]:
    run = _mapping(raw, "workflow run")
    run_id = _integer(run, "id")
    run_attempt = _integer(run, "run_attempt")
    actual_workflow = _string(run, "path")
    if actual_workflow != workflow_path:
        raise PermissionError(
            f"workflow run {run_id} uses {actual_workflow!r}, not {workflow_path!r}"
        )
    head_sha = _validate_sha(_string(run, "head_sha"), "workflow run head_sha")
    if expected_source_revision is not None and head_sha != expected_source_revision:
        raise PermissionError(
            f"workflow run {run_id} source revision does not match the expected release revision"
        )
    status = _string(run, "status")
    conclusion_value = run.get("conclusion")
    conclusion = conclusion_value if isinstance(conclusion_value, str) else ""
    event_value = run.get("event")
    event = event_value if isinstance(event_value, str) else ""
    branch_value = run.get("head_branch")
    head_branch = branch_value if isinstance(branch_value, str) else ""
    url_value = run.get("html_url")
    html_url = url_value if isinstance(url_value, str) else ""
    return {
        "run_id": run_id,
        "run_attempt": run_attempt,
        "head_sha": head_sha,
        "status": status,
        "conclusion": conclusion,
        "event": event,
        "head_branch": head_branch,
        "html_url": html_url,
        "workflow_path": actual_workflow,
    }


def _require_success(run: Mapping[str, object]) -> dict[str, object]:
    status = cast(str, run["status"])
    conclusion = cast(str, run["conclusion"])
    run_id = cast(int, run["run_id"])
    if status != "completed" or conclusion != "success":
        state = conclusion or status
        raise RuntimeError(
            f"Release Verification run {run_id} is not successful (state={state!r})"
        )
    return dict(run)


def _matching_runs(
    payload: object,
    *,
    workflow_path: str,
    expected_source_revision: str,
) -> list[dict[str, object]]:
    root = _mapping(payload, "workflow runs response")
    raw_runs = root.get("workflow_runs")
    if not isinstance(raw_runs, list):
        raise ValueError("workflow runs response is missing workflow_runs")
    runs: list[dict[str, object]] = []
    for raw in raw_runs:
        try:
            run = _validated_run(
                raw,
                workflow_path=workflow_path,
                expected_source_revision=expected_source_revision,
            )
        except (PermissionError, ValueError):
            continue
        runs.append(run)
    runs.sort(
        key=lambda item: (cast(int, item["run_id"]), cast(int, item["run_attempt"])),
        reverse=True,
    )
    return runs


def resolve_run(
    *,
    repository: str,
    workflow_path: str,
    run_id: int | None,
    expected_source_revision: str | None,
    wait_seconds: float,
    poll_seconds: float,
    token: str,
) -> dict[str, object]:
    """Resolve an explicit run or wait for the newest matching release verification."""
    repository = _validate_repository(repository)
    if wait_seconds < 0:
        raise ValueError("wait-seconds must be non-negative")
    if poll_seconds <= 0:
        raise ValueError("poll-seconds must be positive")
    expected = (
        _validate_sha(expected_source_revision, "expected source revision")
        if expected_source_revision
        else None
    )
    if run_id is not None:
        if run_id <= 0:
            raise ValueError("run-id must be positive")
        return _require_success(
            _validated_run(
                _api_json(repository, f"/actions/runs/{run_id}", token=token),
                workflow_path=workflow_path,
                expected_source_revision=expected,
            )
        )
    if expected is None:
        raise ValueError("expected-source-revision is required when run-id is omitted")

    workflow_file = Path(workflow_path).name
    query = urllib.parse.urlencode(
        {"head_sha": expected, "per_page": "20"}, quote_via=urllib.parse.quote
    )
    endpoint = (
        f"/actions/workflows/{urllib.parse.quote(workflow_file, safe='')}/runs?{query}"
    )
    deadline = _monotonic() + wait_seconds
    while True:
        runs = _matching_runs(
            _api_json(repository, endpoint, token=token),
            workflow_path=workflow_path,
            expected_source_revision=expected,
        )
        if runs:
            newest = runs[0]
            status = cast(str, newest["status"])
            conclusion = cast(str, newest["conclusion"])
            if status == "completed":
                if conclusion == "success":
                    return newest
                run_number = cast(int, newest["run_id"])
                raise RuntimeError(
                    f"newest Release Verification run {run_number} completed with "
                    f"{conclusion or 'unknown'!r}"
                )
        if _monotonic() >= deadline:
            raise TimeoutError(
                "timed out waiting for a successful Release Verification run for "
                f"source revision {expected}"
            )
        _sleep(poll_seconds)


def _write_github_output(path: Path, run: Mapping[str, object]) -> None:
    lines = (
        f"run_id={run['run_id']}",
        f"run_attempt={run['run_attempt']}",
        f"head_sha={run['head_sha']}",
        f"event={run['event']}",
        f"head_branch={run['head_branch']}",
        f"html_url={run['html_url']}",
    )
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        for line in lines:
            handle.write(line + "\n")


def main() -> int:
    """Resolve the exact successful Release Verification run for publication."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--workflow-path", default=DEFAULT_WORKFLOW_PATH)
    parser.add_argument("--run-id", type=int)
    parser.add_argument("--expected-source-revision")
    parser.add_argument("--wait-seconds", type=float, default=1800.0)
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()

    run = resolve_run(
        repository=args.repository,
        workflow_path=args.workflow_path,
        run_id=args.run_id,
        expected_source_revision=args.expected_source_revision,
        wait_seconds=args.wait_seconds,
        poll_seconds=args.poll_seconds,
        token=_token(),
    )
    if args.github_output is not None:
        _write_github_output(args.github_output, run)
    print(json.dumps(run, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
