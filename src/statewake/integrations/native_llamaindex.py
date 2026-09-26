"""Native LlamaIndex instrumentation event handler attachment."""

from __future__ import annotations

from collections import deque
from datetime import UTC, datetime
from typing import Any

from statewake.ai_contracts.retrieval import RetrievalEvidenceContract
from statewake.integrations.base import capture_contract, digest_json

from .native_capture import (
    NativeCaptureSink,
    capture_native_observation,
    safe_metadata,
    utc_time,
)


def _query_text(value: object) -> str | None:
    """Return only an explicitly observed LlamaIndex query string."""
    if isinstance(value, str):
        return value
    query = getattr(value, "query_str", None)
    return query if isinstance(query, str) else None


def _event_time(event: object) -> tuple[datetime, str, str]:
    """Resolve an honest observation time without assigning a zone to naive time."""
    native = getattr(event, "timestamp", None)
    if native is None:
        raise ValueError("LlamaIndex event has no timestamp")
    if isinstance(native, datetime) and (
        native.tzinfo is None or native.utcoffset() is None
    ):
        # LlamaIndex 0.14.x constructs instrumentation events with naive datetimes.
        # Their timezone semantics are not part of the observed event, so preserve
        # the event with StateWake's own receipt instant rather than fabricating UTC.
        return (
            datetime.now(UTC),
            "adapter_receipt_time",
            "native_datetime_timezone_unspecified",
        )
    return utc_time(native), "native_event_time", "timezone_aware"


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
            exc.name in {"llama_index", "llama_index_instrumentation"}
            or exc.name.startswith("llama_index.")
        ):
            raise
        raise ImportError(
            "Install statewake-ai[integrations-llamaindex] for native instrumentation"
        ) from exc

    # State is deliberately adapter-local and bounded. Query text itself is never
    # retained: only its digest is correlated from RetrievalStartEvent to EndEvent.
    retrieval_queries: dict[str, str] = {}
    retrieval_order: deque[str] = deque()
    seen_event_ids: set[str] = set()
    seen_order: deque[str] = deque()
    state_limit = 4096

    def remember_query(key: str, query_digest: str) -> None:
        """Retain one bounded retrieval query digest for start/end correlation."""
        if key not in retrieval_queries:
            retrieval_order.append(key)
        retrieval_queries[key] = query_digest
        while len(retrieval_order) > state_limit:
            expired = retrieval_order.popleft()
            retrieval_queries.pop(expired, None)

    def first_event(event_id: str) -> bool:
        """Return whether this bounded native event identity is newly observed."""
        if event_id in seen_event_ids:
            return False
        seen_event_ids.add(event_id)
        seen_order.append(event_id)
        while len(seen_order) > state_limit:
            seen_event_ids.discard(seen_order.popleft())
        return True

    class StateWakeLlamaIndexHandler(BaseEventHandler):
        """Capture native event IDs/classes without persisting SDK payload text."""

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
                event_id = str(event_id)
                if not first_event(event_id):
                    return
                operation = (
                    event.class_name()
                    if callable(getattr(event, "class_name", None))
                    else type(event).__name__
                )
                if getattr(event, "timestamp", None) is None:
                    sink.fail(
                        "llamaindex.timestamp_missing",
                        ValueError("LlamaIndex event has no timestamp"),
                    )
                    return
                try:
                    timestamp, timestamp_origin, timestamp_status = _event_time(event)
                except ValueError as exc:
                    sink.fail("llamaindex.timestamp_invalid", exc)
                    return

                span_key = str(getattr(event, "span_id", None) or event_id)
                if operation == "RetrievalStartEvent":
                    query = _query_text(getattr(event, "str_or_query_bundle", None))
                    if query is None:
                        sink.fail(
                            "llamaindex.retrieval_start",
                            ValueError("missing observed retrieval query"),
                        )
                    else:
                        remember_query(span_key, digest_json(query))

                if operation == "RetrievalEndEvent":
                    context = getattr(event, "str_or_query_bundle", None)
                    query = _query_text(context)
                    query_digest = (
                        digest_json(query)
                        if query is not None
                        else retrieval_queries.pop(span_key, None)
                    )
                    nodes = getattr(event, "nodes", None)
                    if (
                        not all(
                            (corpus_identity, corpus_snapshot_id, citation_boundary)
                        )
                        or query_digest is None
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
                            if not corpus_identity or not citation_boundary:
                                raise ValueError(
                                    "native retrieval requires corpus and citation identity"
                                )
                            digests = tuple(
                                digest_json(item.node.get_content()) for item in items
                            )
                            sink.add(
                                capture_contract(
                                    RetrievalEvidenceContract(
                                        contract_version="llamaindex.native.retrieval.v1",
                                        producer_id="llamaindex-native",
                                        run_id=event_id,
                                        corpus_identity=corpus_identity,
                                        corpus_snapshot_id=corpus_snapshot_id,
                                        query_digest=query_digest,
                                        retrieved_item_ids=ids,
                                        chunk_digests=digests,
                                        citation_boundary=citation_boundary,
                                        captured_at=timestamp,
                                        metadata={
                                            "source": "native-instrumentation",
                                            "timestamp_origin": timestamp_origin,
                                            "native_timestamp_status": timestamp_status,
                                        },
                                    )
                                )
                            )
                        except (ValueError, TypeError, AttributeError) as exc:
                            sink.fail("llamaindex.retrieval_contract", exc)
                    retrieval_queries.pop(span_key, None)

                capture_native_observation(
                    sink,
                    framework="llamaindex",
                    run_id=event_id,
                    trace_id=span_key,
                    span_id=event_id,
                    observed_at=timestamp,
                    observation_kind="instrumentation_event",
                    metadata=safe_metadata(
                        event_kind="instrumentation_event",
                        operation=operation,
                        timestamp_origin=timestamp_origin,
                        native_timestamp_status=timestamp_status,
                    ),
                )
            except (ValueError, AttributeError, TypeError) as exc:
                sink.fail("llamaindex.event", exc)

    return StateWakeLlamaIndexHandler()


def attach_llamaindex_event_handler(
    sink: NativeCaptureSink,
    *,
    dispatcher_name: str | None = None,
    corpus_identity: str | None = None,
    corpus_snapshot_id: str | None = None,
    citation_boundary: str | None = None,
) -> Any:
    """Attach to LlamaIndex's root dispatcher by default.

    LlamaIndex module dispatchers created before a late named attachment are not
    reliably observed through a newly requested ``llama_index`` dispatcher. The
    root dispatcher is the SDK-supported broad instrumentation boundary. Callers
    may still request a specific dispatcher when intentionally scoping capture.
    """
    try:
        from llama_index_instrumentation import get_dispatcher

    except ModuleNotFoundError as exc:
        if exc.name is None or not (
            exc.name in {"llama_index", "llama_index_instrumentation"}
            or exc.name.startswith("llama_index.")
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
    dispatcher = (
        get_dispatcher() if dispatcher_name is None else get_dispatcher(dispatcher_name)
    )
    dispatcher.add_event_handler(handler)
    return handler


def detach_llamaindex_event_handler(
    handler: Any, *, dispatcher_name: str | None = None
) -> None:
    """Detach a previously attached handler without assuming a single SDK API."""
    try:
        from llama_index_instrumentation import get_dispatcher
    except ModuleNotFoundError as exc:
        if exc.name is None or not (
            exc.name == "llama_index" or exc.name.startswith("llama_index.")
        ):
            raise
        raise ImportError(
            "Install statewake-ai[integrations-llamaindex] for native instrumentation"
        ) from exc
    dispatcher = (
        get_dispatcher() if dispatcher_name is None else get_dispatcher(dispatcher_name)
    )
    remove = getattr(dispatcher, "remove_event_handler", None)
    if callable(remove):
        remove(handler)
        return
    handlers = getattr(dispatcher, "event_handlers", None)
    if isinstance(handlers, list):
        for index, current in enumerate(tuple(handlers)):
            if current is handler:
                handlers.pop(index)
                return
    raise ValueError("LlamaIndex dispatcher cannot detach the supplied handler")
