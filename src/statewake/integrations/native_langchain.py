"""Native LangChain callback handler for model, tool, and retriever lifecycles."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

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
            self._started: dict[str, tuple[datetime, str | None, str, str, bool]] = {}
            self._model_inputs: dict[str, str] = {}
            self._tool_inputs: dict[str, str] = {}
            self._queries: dict[str, str] = {}

        @staticmethod
        def _identity(value: Any) -> str:
            """Require a native string or UUID callback identity."""
            if not isinstance(value, (str, UUID)) or not str(value).strip():
                raise ValueError("missing native callback identity")
            return str(value)

        @staticmethod
        def _operation(
            serialized: Mapping[str, Any] | None, kind: str
        ) -> tuple[str, bool]:
            """Admit a bounded name or a fixed non-payload operation label."""
            try:
                name = (
                    serialized.get("name") if isinstance(serialized, Mapping) else None
                )
            except Exception:
                name = None
            if isinstance(name, str) and re.fullmatch(
                r"[A-Za-z][A-Za-z0-9_.-]{0,63}", name
            ):
                return name, True
            return kind, False

        def _start(
            self,
            run_id: Any,
            parent_run_id: Any,
            kind: str,
            name: str,
            observed_name: bool,
        ) -> str:
            identity = self._identity(run_id)
            if identity in self._started:
                raise ValueError("duplicate callback start")
            if len(self._started) >= sink.capacity:
                raise ValueError("callback start window exhausted")
            parent = (
                self._identity(parent_run_id) if parent_run_id is not None else None
            )
            self._started[identity] = (
                datetime.now(UTC),
                parent,
                kind,
                name,
                observed_name,
            )
            return identity

        def _finish(self, run_id: Any, error: bool = False) -> None:
            try:
                identity = self._identity(run_id)
            except ValueError as exc:
                sink.fail("langchain.unpaired_callback", exc)
                return
            entry = self._started.pop(identity, None)
            if entry is None:
                sink.fail("langchain.unpaired_callback", ValueError("missing start"))
                return
            started, parent, kind, name, _ = entry
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
            serialized: Mapping[str, Any] | None,
            prompts: list[str],
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """Observe a text-generation start without retaining prompts."""
            try:
                name, observed = self._operation(serialized, "llm")
                digest = digest_sdk_observed(prompts)
                identity = self._start(run_id, parent_run_id, "llm", name, observed)
                self._model_inputs[identity] = digest
            except (ValueError, TypeError, AttributeError) as exc:
                sink.fail("langchain.llm_start", exc)

        def on_chat_model_start(
            self,
            serialized: Mapping[str, Any] | None,
            messages: list[Any],
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """Observe chat model start without retaining messages."""
            try:
                name, observed = self._operation(serialized, "chat_model")
                digest = digest_sdk_observed(messages)
                identity = self._start(
                    run_id, parent_run_id, "chat_model", name, observed
                )
                self._model_inputs[identity] = digest
            except (ValueError, TypeError, AttributeError) as exc:
                sink.fail("langchain.chat_model_start", exc)

        def on_llm_end(self, response: Any, *, run_id: Any, **kwargs: Any) -> None:
            """Complete a model callback."""
            identity = str(run_id)
            entry = self._started.get(identity)
            input_digest = self._model_inputs.pop(identity, None)
            if entry is not None and input_digest is not None and entry[4]:
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
                                model_version_omission_reason=(
                                    "No version supplied by callback"
                                ),
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
            elif entry is not None and input_digest is not None:
                sink.fail("langchain.model_identity", ValueError("missing model name"))
            self._finish(run_id)

        def on_llm_error(
            self, error: BaseException, *, run_id: Any, **kwargs: Any
        ) -> None:
            """Record model failure without the potentially sensitive exception."""
            self._model_inputs.pop(str(run_id), None)
            self._finish(run_id, error=True)

        def on_tool_start(
            self,
            serialized: Mapping[str, Any] | None,
            input_str: str,
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """Observe tool start without retaining input."""
            try:
                name, observed = self._operation(serialized, "tool")
                digest = digest_json(input_str)
                identity = self._start(run_id, parent_run_id, "tool", name, observed)
                self._tool_inputs[identity] = digest
            except (ValueError, TypeError, AttributeError) as exc:
                sink.fail("langchain.tool_start", exc)

        def on_tool_end(self, output: Any, *, run_id: Any, **kwargs: Any) -> None:
            """Complete a tool callback; execution alone is not authorization."""
            identity = str(run_id)
            entry = self._started.get(identity)
            input_digest = self._tool_inputs.pop(identity, None)
            if entry is not None and input_digest is not None and entry[4]:
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
            elif entry is not None and input_digest is not None:
                sink.fail("langchain.tool_identity", ValueError("missing tool name"))
            self._finish(run_id)

        def on_tool_error(
            self, error: BaseException, *, run_id: Any, **kwargs: Any
        ) -> None:
            """Capture tool failure."""
            self._tool_inputs.pop(str(run_id), None)
            self._finish(run_id, error=True)

        def on_retriever_start(
            self,
            serialized: Mapping[str, Any] | None,
            query: str,
            *,
            run_id: Any,
            parent_run_id: Any = None,
            **kwargs: Any,
        ) -> None:
            """Observe retriever start without retaining query."""
            try:
                if not isinstance(query, str):
                    raise ValueError("retrieval query must be observed text")
                _, observed = self._operation(serialized, "retriever")
                name = "retriever"
                digest = digest_json(query)
                identity = self._start(
                    run_id, parent_run_id, "retriever", name, observed
                )
                self._queries[identity] = digest
            except (ValueError, TypeError, AttributeError) as exc:
                sink.fail("langchain.retriever_start", exc)

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
                        ids: list[str] = []
                        contents: list[str] = []
                        for doc in docs:
                            item_id = getattr(doc, "id", None)
                            content = getattr(doc, "page_content", None)
                            if not isinstance(item_id, str) or not item_id.strip():
                                raise ValueError(
                                    "retrieved documents lack stable native IDs"
                                )
                            if not isinstance(content, str):
                                raise ValueError(
                                    "retrieved document content is not text"
                                )
                            ids.append(item_id)
                            contents.append(content)
                        if not ids:
                            raise ValueError(
                                "retrieved documents lack stable native IDs"
                            )
                        digests = tuple(digest_json(content) for content in contents)
                        sink.add(
                            capture_contract(
                                RetrievalEvidenceContract(
                                    contract_version="langchain.native.retrieval.v1",
                                    producer_id="langchain-native",
                                    run_id=identity,
                                    corpus_identity=corpus_identity,
                                    corpus_snapshot_id=corpus_snapshot_id,
                                    query_digest=query_digest,
                                    retrieved_item_ids=tuple(ids),
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
