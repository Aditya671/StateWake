"""Regression coverage for OpenAI Agents response span evidence admission."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from hashlib import sha256
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from statewake.integrations.native_capture import NativeCaptureSink
from statewake.integrations.native_openai_agents import create_agents_trace_processor


@contextmanager
def processor_with_fake_sdk() -> Iterator[tuple[Any, NativeCaptureSink]]:
    """Supply the SDK processor interface without replacing the adapter."""
    agents = ModuleType("agents")
    tracing = ModuleType("agents.tracing")
    interface = ModuleType("agents.tracing.processor_interface")
    interface.TracingProcessor = type(  # type: ignore[attr-defined]
        "TracingProcessor", (), {}
    )
    with patch.dict(
        sys.modules,
        {
            "agents": agents,
            "agents.tracing": tracing,
            "agents.tracing.processor_interface": interface,
        },
    ):
        sink = NativeCaptureSink()
        yield create_agents_trace_processor(sink), sink


def response_span(
    *,
    input_value: object = "secret-request-marker",
    response: object | None = None,
    error: object | None = None,
    span_id: str = "span-response",
) -> SimpleNamespace:
    """Mimic the SDK's completed span shape, keeping content in memory."""
    if response is None:
        response = SimpleNamespace(
            model="test-model",
            model_dump=lambda *, mode: {
                "model": "test-model",
                "output": [{"text": "secret-response-marker"}],
            },
        )
    return SimpleNamespace(
        trace_id="trace-1",
        span_id=span_id,
        parent_id=None,
        started_at="2026-09-25T00:00:00Z",
        ended_at="2026-09-25T00:00:01Z",
        error=error,
        span_data=SimpleNamespace(
            type="response", input=input_value, response=response
        ),
    )


def canonical_digest(value: object) -> str:
    """Independently compute the specified complete JSON envelope digest."""
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def test_response_span_captures_entire_envelope_once_and_redacts_payload() -> None:
    """A replay cannot add a second model invocation or runtime trace."""
    with processor_with_fake_sdk() as (processor, sink):
        span = response_span(input_value=[{"content": "secret-request-marker"}])
        processor.on_span_end(span)
        processor.on_span_end(span)
        results = sink.snapshot()
        assert [item.payload["contract_type"] for item in results] == [
            "runtime_trace",
            "model_invocation",
        ]
        model = results[1].payload
        assert model["run_id"] == "span-response"
        assert model["metadata"] == {"trace_id": "trace-1", "span_id": "span-response"}
        assert model["model_name"] == "test-model"
        assert model["request_digest"] == canonical_digest(
            [{"content": "secret-request-marker"}]
        )
        assert model["response_digest"] == canonical_digest(
            {"model": "test-model", "output": [{"text": "secret-response-marker"}]}
        )
        assert not sink.failures
        persisted = str([item.payload for item in results]) + str(sink.failures)
        assert "secret-request-marker" not in persisted
        assert "secret-response-marker" not in persisted


@pytest.mark.parametrize(
    ("request_value", "response"),
    [
        (None, SimpleNamespace(model="m")),
        ("request", SimpleNamespace(model=None)),
        ("request", SimpleNamespace(model="  ")),
        ("request", SimpleNamespace(model=object())),
    ],
)
def test_incomplete_response_journals_a_specific_failure(
    request_value: object, response: object
) -> None:
    """Runtime observation remains, but no invented model evidence appears."""
    with processor_with_fake_sdk() as (processor, sink):
        processor.on_span_end(
            response_span(input_value=request_value, response=response)
        )
        assert [item.payload["contract_type"] for item in sink.snapshot()] == [
            "runtime_trace"
        ]
        assert sink.failures == ["agents.response_missing: ValueError"]


def test_redacted_response_without_output_is_incomplete() -> None:
    """SDK tracing redaction cannot produce a success contract."""
    with processor_with_fake_sdk() as (processor, sink):
        span = response_span()
        span.span_data.response = None
        processor.on_span_end(span)
        assert [item.payload["contract_type"] for item in sink.snapshot()] == [
            "runtime_trace"
        ]
        assert sink.failures == ["agents.response_missing: ValueError"]


@pytest.mark.parametrize(
    "request_value,response",
    [
        (b"binary", SimpleNamespace(model="m", model_dump=lambda *, mode: {})),
        ("request", SimpleNamespace(model="m", model_dump=lambda *, mode: object())),
        (
            "request",
            SimpleNamespace(model="m", model_dump=lambda *, mode: {"n": float("nan")}),
        ),
        (
            "request",
            SimpleNamespace(model="m", model_dump=lambda *, mode: {1: "value"}),
        ),
    ],
)
def test_unserializable_response_fails_closed(
    request_value: object, response: object
) -> None:
    """Neither object repr nor invalid JSON can stand in for observed content."""
    with processor_with_fake_sdk() as (processor, sink):
        processor.on_span_end(
            response_span(input_value=request_value, response=response)
        )
        assert [item.payload["contract_type"] for item in sink.snapshot()] == [
            "runtime_trace"
        ]
        assert sink.failures == ["agents.response_contract: ValueError"]


def test_error_response_span_has_only_error_runtime_evidence() -> None:
    """An SDK error cannot be advertised as a successful model invocation."""
    with processor_with_fake_sdk() as (processor, sink):
        processor.on_span_end(response_span(error={"message": "secret-error"}))
        assert [item.payload["contract_type"] for item in sink.snapshot()] == [
            "runtime_trace"
        ]
        assert sink.snapshot()[0].payload["error_status"] == "error"
        assert "secret-error" not in str(sink.snapshot()[0].payload)


def test_missing_native_identity_is_not_an_invented_run_id() -> None:
    """A malformed SDK span is journaled without a synthetic identity."""
    with processor_with_fake_sdk() as (processor, sink):
        processor.on_span_end(response_span(span_id=""))
        assert not sink.snapshot()
        assert sink.failures == ["agents.span_end: ValueError"]


def test_sdk_response_span_data_shape_if_installed() -> None:
    """Check the real SDK type, independently of the fake module fixture."""
    sdk = pytest.importorskip("agents.tracing.span_data")
    data = sdk.ResponseSpanData(
        input="secret-request-marker",
        response=SimpleNamespace(
            model="test-model",
            model_dump=lambda *, mode: {"model": "test-model", "output": []},
        ),
    )
    sink = NativeCaptureSink()
    processor = create_agents_trace_processor(sink)
    span = response_span()
    span.span_data = data
    processor.on_span_end(span)
    assert [item.payload["contract_type"] for item in sink.snapshot()] == [
        "runtime_trace",
        "model_invocation",
    ]
    assert not sink.failures
