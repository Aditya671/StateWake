"""New regression coverage for native evidence integrity boundaries."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from hashlib import sha256
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

import pytest

from statewake.integrations.native_capture import (
    NativeCaptureSink,
    capture_native_runtime,
    digest_observed,
)
from statewake.integrations.native_openai_agents import create_agents_trace_processor


def test_completed_observation_rejects_missing_timestamps() -> None:
    """Never invent a timestamp for a completed native observation."""
    sink = NativeCaptureSink()
    timestamp = datetime(2026, 9, 23, tzinfo=UTC)
    for start, end in ((None, timestamp), (timestamp, None)):
        with pytest.raises(ValueError, match="start and end"):
            capture_native_runtime(
                sink,
                framework="test",
                run_id="run",
                trace_id="trace",
                span_id="span",
                started_at=start,
                ended_at=end,
            )
    assert sink.snapshot() == ()


def test_structured_native_digest_is_canonical_and_rejects_opaque() -> None:
    """Input ordering and object repr must never govern evidence identity."""
    first = [{"b": 2, "a": 1}]
    second = [{"a": 1, "b": 2}]
    expected = sha256(
        json.dumps(
            first,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode()
    ).hexdigest()
    assert digest_observed(first) == digest_observed(second) == expected
    with pytest.raises(ValueError, match="not JSON-serializable"):
        digest_observed(object())


def test_openai_native_model_digest_uses_structured_payload() -> None:
    """OpenAI generation evidence uses observed JSON, not Python list repr."""
    agents = ModuleType("agents")
    tracing = ModuleType("agents.tracing")

    class TracingProcessor:
        pass

    tracing.TracingProcessor = TracingProcessor  # type: ignore[attr-defined]
    processor_interface = ModuleType("agents.tracing.processor_interface")
    processor_interface.TracingProcessor = TracingProcessor  # type: ignore[attr-defined]
    with patch.dict(
        sys.modules,
        {
            "agents": agents,
            "agents.tracing": tracing,
            "agents.tracing.processor_interface": processor_interface,
        },
    ):
        sink = NativeCaptureSink()
        processor = create_agents_trace_processor(sink)
        input_data = [{"b": 2, "a": 1}]
        span = SimpleNamespace(
            trace_id="trace",
            span_id="span",
            parent_id=None,
            started_at="2026-09-23T00:00:00Z",
            ended_at="2026-09-23T00:00:01Z",
            error=None,
            span_data=SimpleNamespace(
                type="generation",
                model="local",
                input=input_data,
                output=[{"message": "secret output"}],
            ),
        )
        processor.on_span_end(span)
        assert not sink.failures
        model = next(
            item
            for item in sink.snapshot()
            if item.payload["contract_type"] == "model_invocation"
        )
        assert model.payload["request_digest"] == digest_observed(input_data)
        assert "secret output" not in str(model.payload)


def test_langchain_native_digest_respects_json_model_and_rejects_repr() -> None:
    """SDK model evidence must not change with Python object representation."""
    from statewake.integrations.native_capture import digest_sdk_observed

    class Message:
        def model_dump(self, *, mode: str) -> dict[str, object]:
            assert mode == "json"
            return {"type": "human", "content": "private question"}

        def __repr__(self) -> str:
            raise AssertionError("SDK repr must not be accessed")

    assert digest_sdk_observed([Message()]) == digest_observed(
        [{"type": "human", "content": "private question"}]
    )
    with pytest.raises(ValueError, match="no supported JSON serialization"):
        digest_sdk_observed(object())


def test_langchain_callback_hashes_native_json_models_not_repr() -> None:
    """Correlate an actual callback lifecycle without hashing a model repr."""
    from uuid import uuid4

    from statewake.integrations.native_capture import digest_sdk_observed
    from statewake.integrations.native_langchain import (
        create_langchain_callback_handler,
    )

    langchain_core = ModuleType("langchain_core")
    callbacks = ModuleType("langchain_core.callbacks")

    class BaseCallbackHandler:
        pass

    class SDKModel:
        def __init__(self, content: str) -> None:
            self.content = content

        def model_dump(self, *, mode: str) -> dict[str, str]:
            assert mode == "json"
            return {"content": self.content}

        def __repr__(self) -> str:
            raise AssertionError("SDK model repr is not evidence")

    callbacks.BaseCallbackHandler = BaseCallbackHandler  # type: ignore[attr-defined]
    callback_base = ModuleType("langchain_core.callbacks.base")
    callback_base.BaseCallbackHandler = BaseCallbackHandler  # type: ignore[attr-defined]
    with patch.dict(
        sys.modules,
        {
            "langchain_core": langchain_core,
            "langchain_core.callbacks": callbacks,
            "langchain_core.callbacks.base": callback_base,
        },
    ):
        sink = NativeCaptureSink()
        handler = create_langchain_callback_handler(sink)
        identity = uuid4()
        handler.on_chat_model_start(
            {"name": "local-model"},
            [[SDKModel("private prompt")]],
            run_id=identity,
        )
        handler.on_llm_end(SDKModel("private response"), run_id=identity)
        assert not sink.failures
        model = next(
            item
            for item in sink.snapshot()
            if item.payload["contract_type"] == "model_invocation"
        )
        assert model.payload["request_digest"] == digest_sdk_observed(
            [[SDKModel("private prompt")]]
        )
        assert model.payload["response_digest"] == digest_sdk_observed(
            SDKModel("private response")
        )
        assert "private response" not in str(model.payload)
