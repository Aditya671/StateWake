"""Behavioral tests for publication-time Release Verification resolution."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from scripts.release import resolve_release_verification_run as resolver

WORKFLOW = ".github/workflows/release-verification.yml"
SHA = "a" * 40


def _run(
    *,
    run_id: int,
    status: str = "completed",
    conclusion: str | None = "success",
) -> dict[str, object]:
    return {
        "id": run_id,
        "run_attempt": 1,
        "path": WORKFLOW,
        "head_sha": SHA,
        "status": status,
        "conclusion": conclusion,
        "event": "push",
        "head_branch": "v0.5.1",
        "html_url": f"https://github.example/runs/{run_id}",
    }


def test_explicit_run_must_already_be_successful(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(resolver, "_api_json", lambda *_args, **_kwargs: _run(run_id=7))
    resolved = resolver.resolve_run(
        repository="example/statewake",
        workflow_path=WORKFLOW,
        run_id=7,
        expected_source_revision=None,
        wait_seconds=0,
        poll_seconds=1,
        token="token",
    )
    assert resolved["run_id"] == 7
    assert resolved["head_sha"] == SHA


def test_release_resolution_waits_for_matching_run_to_succeed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses: Iterator[object] = iter(
        (
            {"workflow_runs": []},
            {"workflow_runs": [_run(run_id=9, status="in_progress", conclusion=None)]},
            {"workflow_runs": [_run(run_id=9)]},
        )
    )
    monotonic_values = iter((0.0, 1.0, 2.0, 3.0))
    monkeypatch.setattr(
        resolver, "_api_json", lambda *_args, **_kwargs: next(responses)
    )
    monkeypatch.setattr(resolver, "_monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(resolver, "_sleep", lambda _seconds: None)

    resolved = resolver.resolve_run(
        repository="example/statewake",
        workflow_path=WORKFLOW,
        run_id=None,
        expected_source_revision=SHA,
        wait_seconds=30,
        poll_seconds=1,
        token="token",
    )
    assert resolved["run_id"] == 9


def test_newest_terminal_failure_blocks_older_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        resolver,
        "_api_json",
        lambda *_args, **_kwargs: {
            "workflow_runs": [
                _run(run_id=12, conclusion="failure"),
                _run(run_id=11),
            ]
        },
    )
    with pytest.raises(RuntimeError, match="completed with 'failure'"):
        resolver.resolve_run(
            repository="example/statewake",
            workflow_path=WORKFLOW,
            run_id=None,
            expected_source_revision=SHA,
            wait_seconds=0,
            poll_seconds=1,
            token="token",
        )
