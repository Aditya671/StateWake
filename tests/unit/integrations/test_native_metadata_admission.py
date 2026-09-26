"""Bound identifiers without stringifying opaque producer-controlled payloads."""

from statewake.integrations.native_capture import safe_metadata


def test_native_metadata_rejects_opaque_and_multiline_content() -> None:
    class Dangerous:
        def __str__(self) -> str:
            raise AssertionError("producer __str__ must not be called")

    assert safe_metadata(
        model_name=Dangerous(),
        provider="approved\napi_key: SECRET",
        status="completed",
        thread_id="t" * 200,
        task_count=4,
        unknown="payload",
    ) == {"status": "completed", "task_count": "4"}
