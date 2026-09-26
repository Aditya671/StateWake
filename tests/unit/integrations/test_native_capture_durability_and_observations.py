"""Bounded capture and event-vs-runtime semantics regressions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from statewake.integrations.base import ContractCaptureResult
from statewake.integrations.native_capture import (
    NativeCaptureCapacityError,
    NativeCaptureSink,
    capture_native_observation,
)
from statewake.integrations.native_langgraph import capture_langgraph_history
from statewake.workspace import StateWakeWorkspace


def observe(sink: NativeCaptureSink, suffix: str) -> ContractCaptureResult:
    return capture_native_observation(
        sink,
        framework="langgraph",
        run_id="thread",
        trace_id="thread",
        span_id=suffix,
        observed_at=datetime(2026, 9, 23, tzinfo=UTC),
        observation_kind="checkpoint",
        metadata={"checkpoint_id": suffix},
    )


def test_sink_is_bounded_and_overflow_is_explicit(tmp_path: object) -> None:
    from pathlib import Path

    path = Path(str(tmp_path)) / "failure.jsonl"
    sink = NativeCaptureSink(capacity=1, failure_capacity=1, failure_journal=path)
    observe(sink, "c1")
    with pytest.raises(NativeCaptureCapacityError):
        observe(sink, "c2")
    assert len(sink.snapshot()) == 1
    assert sink.failure_count == 1
    assert (
        json.loads(path.read_text().strip())["error_type"]
        == "NativeCaptureCapacityError"
    )
    assert sink.drain()[0].payload["span_id"] == "c1"
    assert sink.snapshot() == ()
    observe(sink, "c3")


def test_failure_journal_replay_is_bounded_and_redacted(tmp_path: object) -> None:
    from pathlib import Path

    path = Path(str(tmp_path)) / "failures.jsonl"
    sink = NativeCaptureSink(failure_journal=path, failure_capacity=2)
    for index in range(5):
        sink.fail("sdk.error", ValueError(f"private-token-{index}"))
    assert sink.failure_count == 5
    assert sink.failures == ["sdk.error: ValueError"] * 2
    restored = NativeCaptureSink(failure_journal=path, failure_capacity=2)
    assert restored.failure_count == 5
    assert restored.failures == sink.failures
    assert "private-token" not in path.read_text()


def test_workspace_sink_persists_before_ack(tmp_path: Path) -> None:
    root = tmp_path
    with pytest.raises(ValueError, match="failure journal"):
        NativeCaptureSink(workspace=StateWakeWorkspace.open(root / "invalid"))
    workspace = StateWakeWorkspace.open(root / "workspace")
    sink = NativeCaptureSink(
        workspace=workspace, failure_journal=root / "failures.jsonl"
    )
    result = observe(sink, "checkpoint-1")
    assert sink.snapshot()[0].digest == result.digest
    assert result.payload["contract_type"] == "observation"
    assert "started_at" not in result.payload
    assert "ended_at" not in result.payload
    workspace.close()


def test_langgraph_checkpoint_does_not_claim_completed_execution() -> None:
    snapshot = SimpleNamespace(
        values={"answer": "private"},
        config={"configurable": {"thread_id": "thread", "checkpoint_id": "c1"}},
        parent_config=None,
        created_at="2026-09-23T00:00:00Z",
        tasks=(),
        interrupts=(),
    )

    class Graph:
        def get_state_history(
            self, config: object, *, limit: object = None
        ) -> list[object]:
            return [snapshot]

    sink = NativeCaptureSink()
    (result,) = capture_langgraph_history(
        Graph(), {"configurable": {"thread_id": "thread"}}, sink
    )
    assert result.payload["contract_type"] == "observation"
    assert result.payload["observation_kind"] == "checkpoint"
    assert "started_at" not in result.payload
    assert "ended_at" not in result.payload
    assert "private" not in str(result.payload)
