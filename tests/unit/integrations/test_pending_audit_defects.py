"""Negative regression cases for unresolved whole-artifact audit findings."""

from datetime import UTC, datetime

import pytest

from statewake.ai_contracts.runtime import RuntimeTraceContract
from statewake.integrations.base import capture_contract
from statewake.integrations.native_capture import NativeCaptureSink
from statewake.integrations.native_opentelemetry import create_genai_span_processor


def _result():
    now = datetime(2026, 9, 23, tzinfo=UTC)
    return capture_contract(
        RuntimeTraceContract(
            contract_version="test.v1",
            producer_id="tester",
            run_id="run",
            framework="test",
            trace_id="trace",
            span_id="span",
            started_at=now,
            ended_at=now,
            captured_at=now,
        )
    )


def test_persist_rejects_missing_timestamp_instead_of_inventing_capture_time(tmp_path):
    from statewake.workspace import StateWakeWorkspace

    result = _result()
    result.payload["captured_at"] = None
    workspace = StateWakeWorkspace.open(tmp_path / "statewake")
    with pytest.raises(ValueError, match="captured_at"):
        result.persist(workspace)


def test_persist_rejects_naive_timestamp_instead_of_local_to_utc(tmp_path):
    from statewake.workspace import StateWakeWorkspace

    result = _result()
    result.payload["captured_at"] = "2026-09-23T00:00:00"
    workspace = StateWakeWorkspace.open(tmp_path / "statewake")
    with pytest.raises(ValueError, match="captured_at"):
        result.persist(workspace)


def test_opentelemetry_does_not_capture_unrelated_spans():
    pytest.importorskip("opentelemetry.sdk.trace")
    from opentelemetry.sdk.trace import TracerProvider

    sink = NativeCaptureSink()
    provider = TracerProvider()
    provider.add_span_processor(create_genai_span_processor(sink))
    tracer = provider.get_tracer("test")
    with tracer.start_as_current_span("http.request"):
        pass
    with tracer.start_as_current_span("chat") as span:
        span.set_attribute("gen_ai.operation.name", "chat")
    provider.shutdown()
    assert len(sink.snapshot()) == 1
    assert not sink.failures


def test_persist_rejects_payload_changed_after_capture(tmp_path):
    """Persisted bytes must still match the evidence digest issued at capture."""
    from statewake.workspace import StateWakeWorkspace

    result = _result()
    result.payload["run_id"] = "altered-after-capture"
    workspace = StateWakeWorkspace.open(tmp_path / "statewake")
    with pytest.raises(ValueError, match="digest"):
        result.persist(workspace)
