"""Native LlamaIndex instrumentation event handler attachment."""

from __future__ import annotations

from typing import Any

from statewake.ai_contracts.retrieval import RetrievalEvidenceContract
from statewake.integrations.base import capture_contract, digest_json

from .native_capture import (
    NativeCaptureSink,
    capture_native_observation,
    safe_metadata,
    utc_time,
)


def create_llamaindex_event_handler(
    sink: NativeCaptureSink,
    *,
    corpus_identity: str | None = None,
    corpus_snapshot_id: str | None = None,
    citation_boundary: str | None = None,
) -> Any:
    """Create a BaseEventHandler compatible with LlamaIndex dispatchers."""
    try:
        from llama_index.core.instrumentation.event_handlers import BaseEventHandler
    except ModuleNotFoundError as exc:
        if exc.name is None or not (
            exc.name == "llama_index" or exc.name.startswith("llama_index.")
        ):
            raise
        raise ImportError(
            "Install statewake-ai[integrations-llamaindex] for native instrumentation"
        ) from exc

    class StateWakeLlamaIndexHandler(BaseEventHandler):
        """Capture native event IDs and classes without storing document text."""

        @classmethod
        def class_name(cls) -> str:
            """Supply the stable identity required by LlamaIndex handlers."""
            return "StateWakeLlamaIndexHandler"

        def handle(self, event: Any, **kwargs: Any) -> None:
            """Handle a real instrumentation event."""
            try:
                event_id = getattr(event, "id_", None) or getattr(event, "id", None)
                if not event_id:
                    raise ValueError("LlamaIndex event has no native identity")
                operation = (
                    event.class_name()
                    if callable(getattr(event, "class_name", None))
                    else type(event).__name__
                )
                observed_timestamp = getattr(event, "timestamp", None)
                if observed_timestamp is None:
                    raise ValueError("LlamaIndex event has no timestamp")
                timestamp = utc_time(observed_timestamp)
                if operation == "RetrievalEndEvent":
                    context = getattr(event, "str_or_query_bundle", None)
                    query = (
                        context
                        if isinstance(context, str)
                        else getattr(context, "query_str", None)
                    )
                    nodes = getattr(event, "nodes", None)
                    if (
                        not all(
                            (corpus_identity, corpus_snapshot_id, citation_boundary)
                        )
                        or query is None
                        or nodes is None
                    ):
                        sink.fail(
                            "llamaindex.retrieval_missing",
                            ValueError("missing observed retrieval context"),
                        )
                    else:
                        try:
                            items = tuple(nodes)
                            ids = tuple(
                                str(getattr(item.node, "node_id", "")) for item in items
                            )
                            if not ids or any(not value for value in ids):
                                raise ValueError(
                                    "native retrieval has no durable node ID"
                                )
                            digests = tuple(
                                digest_json(item.node.get_content()) for item in items
                            )
                            sink.add(
                                capture_contract(
                                    RetrievalEvidenceContract(
                                        contract_version="llamaindex.native.retrieval.v1",
                                        producer_id="llamaindex-native",
                                        run_id=str(event_id),
                                        corpus_identity=corpus_identity,
                                        corpus_snapshot_id=corpus_snapshot_id,
                                        query_digest=digest_json(query),
                                        retrieved_item_ids=ids,
                                        chunk_digests=digests,
                                        citation_boundary=citation_boundary,
                                        captured_at=timestamp,
                                        metadata={"source": "native-instrumentation"},
                                    )
                                )
                            )
                        except (ValueError, TypeError, AttributeError) as exc:
                            sink.fail("llamaindex.retrieval_contract", exc)
                capture_native_observation(
                    sink,
                    framework="llamaindex",
                    run_id=str(event_id),
                    trace_id=str(getattr(event, "span_id", None) or event_id),
                    span_id=str(event_id),
                    observed_at=timestamp,
                    observation_kind="instrumentation_event",
                    metadata=safe_metadata(
                        event_kind="instrumentation_event", operation=operation
                    ),
                )
            except (ValueError, AttributeError, TypeError) as exc:
                sink.fail("llamaindex.event", exc)

    return StateWakeLlamaIndexHandler()


def attach_llamaindex_event_handler(
    sink: NativeCaptureSink,
    *,
    dispatcher_name: str = "llama_index",
    corpus_identity: str | None = None,
    corpus_snapshot_id: str | None = None,
    citation_boundary: str | None = None,
) -> Any:
    """Attach a real event handler to a LlamaIndex instrumentation dispatcher."""
    try:
        from llama_index.core.instrumentation import get_dispatcher
    except ModuleNotFoundError as exc:
        if exc.name is None or not (
            exc.name == "llama_index" or exc.name.startswith("llama_index.")
        ):
            raise
        raise ImportError(
            "Install statewake-ai[integrations-llamaindex] for native instrumentation"
        ) from exc
    handler = create_llamaindex_event_handler(
        sink,
        corpus_identity=corpus_identity,
        corpus_snapshot_id=corpus_snapshot_id,
        citation_boundary=citation_boundary,
    )
    get_dispatcher(dispatcher_name).add_event_handler(handler)
    return handler
