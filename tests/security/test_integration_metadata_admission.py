"""Negative regressions for untrusted producer metadata admission."""

from statewake.integrations.base import metadata_without_payload
from statewake.integrations.opentelemetry_genai import capture_genai_runtime_trace


def test_arbitrary_secret_and_nested_metadata_is_not_persisted() -> None:
    result = metadata_without_payload(
        {
            "run_id": "run-01",
            "trace_id": "trace-01",
            "authorization": "Bearer sensitive-token",
            "gen_ai.input.messages": "secret message",
            "prompt": "secret prompt",
            "nested": {"safe": "no", "api_key": "secret"},
            "error": "Authorization: Bearer sensitive-token",
            "output": {"result": "secret"},
        },
        exclude={"output"},
    )
    assert result == {"run_id": "run-01", "trace_id": "trace-01"}


def test_telemetry_payload_aliases_do_not_enter_contract_metadata() -> None:
    result = capture_genai_runtime_trace(
        {
            "attributes": {
                "statewake.run_id": "run-01",
                "trace_id": "trace-01",
                "span_id": "span-01",
                "gen_ai.operation.name": "chat",
                "start_time": "2026-09-23T00:00:00Z",
                "end_time": "2026-09-23T00:00:00Z",
                "gen_ai.input.messages": "private",
                "gen_ai.output.messages": "more private",
                "error.message": "token=private",
            }
        }
    )
    metadata = result.payload["metadata"]
    assert "private" not in str(metadata)
    assert "gen_ai.operation.name" in metadata
