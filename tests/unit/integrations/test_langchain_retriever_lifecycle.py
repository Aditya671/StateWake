"""LangChain callback lifecycle and evidence admission regressions."""

from __future__ import annotations

import sys
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from hashlib import sha256
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest

from statewake.integrations.native_capture import NativeCaptureSink
from statewake.integrations.native_langchain import create_langchain_callback_handler
from statewake.utils.json_support import JsonValue


@contextmanager
def handler_with_fake_sdk(
    *, corpus: bool = True
) -> Iterator[tuple[Any, NativeCaptureSink]]:
    """Use the actual adapter with only the SDK base class substituted."""
    core = ModuleType("langchain_core")
    callbacks = ModuleType("langchain_core.callbacks")
    callback_base = ModuleType("langchain_core.callbacks.base")
    callback_base.BaseCallbackHandler = type(  # type: ignore[attr-defined]
        "BaseCallbackHandler", (), {}
    )
    with patch.dict(
        sys.modules,
        {
            "langchain_core": core,
            "langchain_core.callbacks": callbacks,
            "langchain_core.callbacks.base": callback_base,
        },
    ):
        sink = NativeCaptureSink()
        handler = create_langchain_callback_handler(
            sink,
            corpus_identity="corpus-1" if corpus else None,
            corpus_snapshot_id="snapshot-1" if corpus else None,
            citation_boundary="doc-id" if corpus else None,
        )
        yield handler, sink


def kinds(sink: NativeCaptureSink) -> list[str]:
    """Return contract kinds without reading raw producer data."""
    return [str(item.payload["contract_type"]) for item in sink.snapshot()]


def object_field(payload: Mapping[str, JsonValue], key: str) -> dict[str, JsonValue]:
    """Narrow one JSON object field for readable contract assertions."""
    value = payload[key]
    assert isinstance(value, dict)
    return value


def test_nullable_retriever_start_captures_complete_evidence() -> None:
    """The observed query and durable document ID survive callback pairing."""
    with handler_with_fake_sdk() as (handler, sink):
        identity, parent = uuid4(), uuid4()
        handler.on_retriever_start(
            None, "private query", run_id=identity, parent_run_id=parent
        )
        handler.on_retriever_end(
            [SimpleNamespace(id="doc-1", page_content="private chunk")],
            run_id=identity,
        )
        assert kinds(sink) == ["retrieval", "runtime_trace"]
        retrieval, runtime = [item.payload for item in sink.snapshot()]
        assert retrieval["run_id"] == str(identity)
        assert retrieval["retrieved_item_ids"] == ["doc-1"]
        assert retrieval["query_digest"] == sha256(b"private query").hexdigest()
        assert retrieval["chunk_digests"] == [sha256(b"private chunk").hexdigest()]
        assert runtime["parent_run_id"] == str(parent)
        assert object_field(runtime, "metadata")["operation"] == "retriever"
        assert sink.failures == []
        assert "private query" not in str([item.payload for item in sink.snapshot()])
        assert "private chunk" not in str([item.payload for item in sink.snapshot()])


@pytest.mark.parametrize(
    ("documents", "failure"),
    [
        ([], "langchain.retrieval_contract: ValueError"),
        (
            [SimpleNamespace(id=None, page_content="text")],
            "langchain.retrieval_contract: ValueError",
        ),
        (
            [SimpleNamespace(id="doc-1", page_content=object())],
            "langchain.retrieval_contract: ValueError",
        ),
    ],
)
def test_inadmissible_documents_keep_paired_runtime(
    documents: list[object], failure: str
) -> None:
    """No synthetic IDs, empty retrieval, or opaque content digest."""
    with handler_with_fake_sdk() as (handler, sink):
        identity = uuid4()
        handler.on_retriever_start(None, "query", run_id=identity)
        handler.on_retriever_end(documents, run_id=identity)
        assert kinds(sink) == ["runtime_trace"]
        assert sink.failures == [failure]


def test_missing_corpus_is_distinct_from_unpaired_callback() -> None:
    """Missing application context cannot be repaired with invented values."""
    with handler_with_fake_sdk(corpus=False) as (handler, sink):
        identity = uuid4()
        handler.on_retriever_start(None, "query", run_id=identity)
        handler.on_retriever_end(
            [SimpleNamespace(id="doc-1", page_content="text")], run_id=identity
        )
        assert kinds(sink) == ["runtime_trace"]
        assert sink.failures == ["langchain.retrieval_context: ValueError"]


def test_opaque_metadata_and_repeated_end_do_not_duplicate_evidence() -> None:
    """A producer object's repr cannot become operation metadata."""

    class Opaque:
        def __repr__(self) -> str:
            raise AssertionError("producer repr must not be evaluated")

    with handler_with_fake_sdk() as (handler, sink):
        identity = uuid4()
        handler.on_retriever_start({"name": Opaque()}, "query", run_id=identity)
        document = SimpleNamespace(id="doc-1", page_content="text")
        handler.on_retriever_end([document], run_id=identity)
        handler.on_retriever_end([document], run_id=identity)
        assert kinds(sink) == ["retrieval", "runtime_trace"]
        assert (
            object_field(sink.snapshot()[1].payload, "metadata")["operation"]
            == "retriever"
        )
        assert sink.failures == ["langchain.unpaired_callback: ValueError"]


def test_duplicate_start_preserves_original_query() -> None:
    """A repeated start cannot replace the first observed digest."""
    with handler_with_fake_sdk() as (handler, sink):
        identity = uuid4()
        handler.on_retriever_start(None, "first query", run_id=identity)
        handler.on_retriever_start(None, "second query", run_id=identity)
        handler.on_retriever_end(
            [SimpleNamespace(id="doc-1", page_content="text")], run_id=identity
        )
        assert (
            sink.snapshot()[0].payload["query_digest"]
            == sha256(b"first query").hexdigest()
        )
        assert sink.failures == ["langchain.retriever_start: ValueError"]


def test_retriever_error_pairs_then_late_completion_is_unpaired() -> None:
    """An error has no successful retrieval and clears temporary query state."""
    with handler_with_fake_sdk() as (handler, sink):
        identity = uuid4()
        handler.on_retriever_start(None, "private query", run_id=identity)
        handler.on_retriever_error(ValueError("private error"), run_id=identity)
        handler.on_retriever_end([], run_id=identity)
        assert kinds(sink) == ["runtime_trace"]
        assert sink.snapshot()[0].payload["error_status"] == "error"
        assert sink.failures == ["langchain.unpaired_callback: ValueError"]
        assert "private error" not in str(sink.snapshot()[0].payload)


def test_invalid_start_is_journaled_without_pairing() -> None:
    """A malformed native run ID cannot become a stringified fake ID."""
    with handler_with_fake_sdk() as (handler, sink):
        handler.on_retriever_start(None, "query", run_id=None)
        assert sink.failures == ["langchain.retriever_start: ValueError"]
        assert kinds(sink) == []


def test_nullable_model_and_tool_names_do_not_invent_typed_identity() -> None:
    """Fallback labels describe runtime only; authorization is not inferred."""
    with handler_with_fake_sdk() as (handler, sink):
        model_id, tool_id = uuid4(), uuid4()
        handler.on_llm_start(None, ["private prompt"], run_id=model_id)
        handler.on_llm_end("private response", run_id=model_id)
        handler.on_tool_start(None, "private input", run_id=tool_id)
        handler.on_tool_end("private output", run_id=tool_id)
        assert kinds(sink) == ["runtime_trace", "runtime_trace"]
        assert sink.failures == [
            "langchain.model_identity: ValueError",
            "langchain.tool_identity: ValueError",
        ]


def test_real_base_retriever_nullable_callback_if_installed() -> None:
    """Exercise a native BaseRetriever event with the pinned SDK in local CI."""
    pytest.importorskip("langchain_core.retrievers")
    documents = pytest.importorskip("langchain_core.documents")
    from langchain_core.retrievers import BaseRetriever

    class LocalRetriever(BaseRetriever):
        def _get_relevant_documents(self, query: str, *, run_manager: Any) -> list[Any]:
            return [documents.Document(id="doc-1", page_content="private chunk")]

    sink = NativeCaptureSink()
    handler = create_langchain_callback_handler(
        sink,
        corpus_identity="corpus-1",
        corpus_snapshot_id="snapshot-1",
        citation_boundary="doc-id",
    )
    observed_serialized: list[object] = []
    original_start = handler.on_retriever_start

    def observe_start(serialized: object, query: str, **kwargs: Any) -> None:
        observed_serialized.append(serialized)
        original_start(serialized, query, **kwargs)

    handler.on_retriever_start = observe_start
    result = LocalRetriever().invoke("private query", config={"callbacks": [handler]})
    assert observed_serialized == [None]
    assert result[0].id == "doc-1"
    assert kinds(sink) == ["retrieval", "runtime_trace"]
    assert sink.failures == []


def test_malformed_serialized_mapping_uses_safe_retriever_label() -> None:
    """Broken producer metadata must not block a valid retrieval lifecycle."""
    from collections.abc import Mapping

    class BrokenMetadata(Mapping[str, object]):
        def __iter__(self) -> Iterator[str]:
            return iter(())

        def __len__(self) -> int:
            return 0

        def __getitem__(self, key: str) -> object:
            raise RuntimeError("private metadata")

        def get(self, key: str, default: object = None) -> object:
            raise RuntimeError("private metadata")

    with handler_with_fake_sdk() as (handler, sink):
        identity = uuid4()
        handler.on_retriever_start(BrokenMetadata(), "query", run_id=identity)
        handler.on_retriever_end(
            [SimpleNamespace(id="doc-1", page_content="text")], run_id=identity
        )
        assert kinds(sink) == ["retrieval", "runtime_trace"]
        assert (
            object_field(sink.snapshot()[1].payload, "metadata")["operation"]
            == "retriever"
        )
        assert not sink.failures


def test_invalid_query_is_a_start_failure_not_query_evidence() -> None:
    """An opaque query is rejected before it can enter the lifecycle map."""
    with handler_with_fake_sdk() as (handler, sink):
        handler.on_retriever_start(None, object(), run_id=uuid4())
        assert not sink.snapshot()
        assert sink.failures == ["langchain.retriever_start: ValueError"]
