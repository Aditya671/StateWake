"""Native LangChain callback handler for model, tool, and retriever lifecycles."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from statewake.ai_contracts.model import ModelInvocationContract
from statewake.ai_contracts.retrieval import RetrievalEvidenceContract
from statewake.ai_contracts.tool import ToolCallContract
from statewake.integrations.base import capture_contract, digest_json

from .native_capture import (
    NativeCaptureSink,
    capture_native_runtime,
    digest_sdk_observed,
    safe_metadata,
)


def create_langchain_callback_handler(
    sink: NativeCaptureSink,
    *,
    corpus_identity: str | None = None,
    corpus_snapshot_id: str | None = None,
    citation_boundary: str | None = None,
    tool_authorizations: dict[str, str] | None = None,
    side_effect_classifications: dict[str, str] | None = None,
) -> Any:
    """Return a real BaseCallbackHandler suitable for a runnable's callbacks."""
    try:
        from langchain_core.callbacks.base import BaseCallbackHandler
    except ModuleNotFoundError as exc:
        if exc.name is None or not (
            exc.name == "langchain_core" or exc.name.startswith("langchain_core.")
        ):
            raise
        raise ImportError(
            "Install statewake-ai[integrations-langchain] for native callbacks"
        ) from exc

    class StateWakeCallbackHandler(BaseCallbackHandler):
        """Correlate native callback starts with ends and errors."""

        def __init__(self) -> None:
            self._started: dict[str, tuple[datetime, str | None, str, str]] = {}
            self._model_inputs: dict[str, str] = {}
            self._tool_inputs: dict[str, str] = {}
            self._queries: dict[str, str] = {}

        def _start(self, run_id: Any, parent_run_id: Any, kind: str, name: str) -> None:
            self._started[str(run_id)] = (
                datetime.now(UTC),
                str(parent_run_id) if parent_run_id else None,
                kind,
                name,
            )

        def _finish(self, run_id: Any, error: bool = False) -> None:
            identity = str(run_id)
            entry = self._started.pop(identity, None)
            if entry is None:
                sink.fail("langchain.unpaired_callback", ValueError("missing start"))
                return
            started, parent, kind, name = entry
            try:
                capture_native_runtime(
                    sink,
                    framework="langchain",
                    run_id=identity,
                    trace_id=parent or identity,
                    span_id=identity,
                    started_at=started,
                    ended_at=datetime.now(UTC),
                    parent_run_id=parent,
                    error_status="error" if error else None,
                    metadata=safe_metadata(event_kind=kind, operation=name),
                )
            except (ValueError, TypeError) as exc:
                sink.fail("langchain.callback", exc)

        def on_llm_start(
            self,
            serialized: dict[str, Any],
            prompts: list[str],
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """Observe a text-generation start without retaining prompts."""
            self._start(
                run_id, parent_run_id, "llm", str(serialized.get("name", "llm"))
            )
            self._model_inputs[str(run_id)] = digest_sdk_observed(prompts)

        def on_chat_model_start(
            self,
            serialized: dict[str, Any],
            messages: list[Any],
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """Observe chat model start without retaining messages."""
            self._start(
                run_id,
                parent_run_id,
                "chat_model",
                str(serialized.get("name", "chat_model")),
            )
            self._model_inputs[str(run_id)] = digest_sdk_observed(messages)

        def on_llm_end(self, response: Any, *, run_id: Any, **kwargs: Any) -> None:
            """Complete a model callback."""
            identity = str(run_id)
            entry = self._started.get(identity)
            input_digest = self._model_inputs.pop(identity, None)
            if entry is not None and input_digest is not None:
                try:
                    model_name = entry[3]
                    sink.add(
                        capture_contract(
                            ModelInvocationContract(
                                contract_version="langchain.native.model.v1",
                                producer_id="langchain-native",
                                run_id=identity,
                                provider="not-recorded-by-producer",
                                model_name=model_name,
                                model_version=None,
                                model_version_omission_reason="No version supplied by callback",
                                parameters={},
                                request_digest=input_digest,
                                response_digest=digest_sdk_observed(response),
                                finish_reason=None,
                                captured_at=datetime.now(UTC),
                                metadata={"source": "native-callback"},
                            )
                        )
                    )
                except (ValueError, TypeError) as exc:
                    sink.fail("langchain.model_contract", exc)
            self._finish(run_id)

        def on_llm_error(
            self, error: BaseException, *, run_id: Any, **kwargs: Any
        ) -> None:
            """Record model failure without the potentially sensitive exception."""
            self._model_inputs.pop(str(run_id), None)
            self._finish(run_id, error=True)

        def on_tool_start(
            self,
            serialized: dict[str, Any],
            input_str: str,
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """Observe tool start without retaining input."""
            self._start(
                run_id, parent_run_id, "tool", str(serialized.get("name", "tool"))
            )
            self._tool_inputs[str(run_id)] = digest_json(input_str)

        def on_tool_end(self, output: Any, *, run_id: Any, **kwargs: Any) -> None:
            """Complete a tool callback; execution alone is not authorization."""
            identity = str(run_id)
            entry = self._started.get(identity)
            input_digest = self._tool_inputs.pop(identity, None)
            if entry is not None and input_digest is not None:
                tool_name = entry[3]
                classification = (side_effect_classifications or {}).get(tool_name)
                authorization = (tool_authorizations or {}).get(tool_name)
                if classification is None or (
                    classification != "none" and not authorization
                ):
                    sink.fail(
                        "langchain.tool_authorization",
                        ValueError("missing policy evidence"),
                    )
                else:
                    try:
                        sink.add(
                            capture_contract(
                                ToolCallContract(
                                    contract_version="langchain.native.tool.v1",
                                    producer_id="langchain-native",
                                    run_id=identity,
                                    tool_name=tool_name,
                                    schema_version="not-recorded-by-producer",
                                    input_digest=input_digest,
                                    output_digest=digest_sdk_observed(output),
                                    execution_status="completed",
                                    side_effect_classification=classification,
                                    authorization_decision=authorization,
                                    captured_at=datetime.now(UTC),
                                    metadata={"source": "native-callback"},
                                )
                            )
                        )
                    except (ValueError, TypeError) as exc:
                        sink.fail("langchain.tool_contract", exc)
            self._finish(run_id)

        def on_tool_error(
            self, error: BaseException, *, run_id: Any, **kwargs: Any
        ) -> None:
            """Capture tool failure."""
            self._tool_inputs.pop(str(run_id), None)
            self._finish(run_id, error=True)

        def on_retriever_start(
            self,
            serialized: dict[str, Any],
            query: str,
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """Observe retriever start without retaining query."""
            self._start(
                run_id,
                parent_run_id,
                "retriever",
                str(serialized.get("name", "retriever")),
            )
            self._queries[str(run_id)] = digest_json(query)

        def on_retriever_end(
            self, documents: Any, *, run_id: Any, **kwargs: Any
        ) -> None:
            """Capture retriever completion without raw documents."""
            identity = str(run_id)
            query_digest = self._queries.pop(identity, None)
            if query_digest is not None:
                if (
                    not corpus_identity
                    or not corpus_snapshot_id
                    or not citation_boundary
                ):
                    sink.fail(
                        "langchain.retrieval_context",
                        ValueError("missing corpus/citation identity"),
                    )
                else:
                    try:
                        docs = tuple(documents)
                        ids = tuple(str(getattr(doc, "id", None) or "") for doc in docs)
                        if not ids or any(not item for item in ids):
                            raise ValueError(
                                "retrieved documents lack stable native IDs"
                            )
                        digests = tuple(
                            digest_json(str(doc.page_content)) for doc in docs
                        )
                        sink.add(
                            capture_contract(
                                RetrievalEvidenceContract(
                                    contract_version="langchain.native.retrieval.v1",
                                    producer_id="langchain-native",
                                    run_id=identity,
                                    corpus_identity=corpus_identity,
                                    corpus_snapshot_id=corpus_snapshot_id,
                                    query_digest=query_digest,
                                    retrieved_item_ids=ids,
                                    chunk_digests=digests,
                                    citation_boundary=citation_boundary,
                                    captured_at=datetime.now(UTC),
                                    metadata={"source": "native-callback"},
                                )
                            )
                        )
                    except (ValueError, TypeError, AttributeError) as exc:
                        sink.fail("langchain.retrieval_contract", exc)
            self._finish(run_id)

        def on_retriever_error(
            self, error: BaseException, *, run_id: Any, **kwargs: Any
        ) -> None:
            """Capture retriever failure."""
            self._queries.pop(str(run_id), None)
            self._finish(run_id, error=True)

    return StateWakeCallbackHandler()
