"""Regression tests for immutable human review-statement persistence."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from statewake.adapters.review_statement import (
    IdempotencyConflictError,
    JsonlReviewStatementStore,
    ReviewSupersessionError,
)


def _append(store: JsonlReviewStatementStore, **changes: object):
    """Append one review fixture using a frozen exact report basis."""
    values: dict[str, object] = {
        "target_record_id": "a" * 64,
        "candidate_identity": "candidate-1",
        "candidate_digest": "b" * 64,
        "report_digest": "c" * 64,
        "profile_id": "rag_answer_verified.v1",
        "profile_version": "1",
        "actor_identity_ref": "reviewer:alice",
        "actor_role": "reliability-reviewer",
        "category": "observation",
        "statement": "The retrieval evidence is present but requires human interpretation.",
        "finding_refs": ("retrieval-evidence",),
        "limitation": "This statement is not an approval.",
        "scope": "candidate review",
        "idempotency_key": "review-request-1",
        "supersedes_digest": None,
    }
    values.update(changes)
    return store.append(**values)  # type: ignore[arg-type]


def test_review_store_is_append_only_hash_linked_and_idempotent(tmp_path: Path) -> None:
    """Persist exact statements once and retain an independently verifiable chain."""
    store = JsonlReviewStatementStore(
        tmp_path / "reviews.jsonl",
        now=lambda: datetime(2026, 9, 27, 10, tzinfo=UTC),
    )
    first, created = _append(store)
    replay, replay_created = _append(store)
    second, second_created = _append(
        store,
        idempotency_key="review-request-2",
        category="question",
        statement="Which corpus version was used?",
    )

    assert created is True
    assert replay_created is False
    assert replay == first
    assert second_created is True
    assert second.sequence == 1
    assert second.previous_digest == first.digest
    assert store.read() == [first, second]


def test_idempotency_key_cannot_be_reused_for_changed_review_text(
    tmp_path: Path,
) -> None:
    """Reject replay ambiguity instead of silently accepting a changed request."""
    store = JsonlReviewStatementStore(tmp_path / "reviews.jsonl")
    _append(store)

    with pytest.raises(IdempotencyConflictError):
        _append(store, statement="changed text")


def test_review_correction_can_only_supersede_same_target_and_author(
    tmp_path: Path,
) -> None:
    """Keep immutable corrections scoped to the original target and author."""
    store = JsonlReviewStatementStore(tmp_path / "reviews.jsonl")
    first, _ = _append(store)
    corrected, created = _append(
        store,
        idempotency_key="review-request-2",
        statement="Corrected observation.",
        supersedes_digest=first.digest,
    )
    assert created is True
    assert corrected.supersedes_digest == first.digest

    with pytest.raises(ReviewSupersessionError):
        _append(
            store,
            idempotency_key="review-request-3",
            actor_identity_ref="reviewer:bob",
            supersedes_digest=first.digest,
        )


def test_tampered_review_text_is_rejected_on_read(tmp_path: Path) -> None:
    """A modified persisted statement must fail its content digest verification."""
    path = tmp_path / "reviews.jsonl"
    store = JsonlReviewStatementStore(path)
    _append(store)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["statement"] = "tampered"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="digest mismatch"):
        store.read()


def test_free_text_saying_approved_remains_only_a_review_statement(
    tmp_path: Path,
) -> None:
    """Never promote natural-language approval wording into approval evidence."""
    store = JsonlReviewStatementStore(tmp_path / "reviews.jsonl")
    record, _ = _append(store, statement="approved", category="review_complete")

    assert record.category == "review_complete"
    assert record.statement == "approved"
    assert "approval_action" not in record.to_dict()


def test_concurrent_idempotent_retries_create_only_one_record(tmp_path: Path) -> None:
    """Serialize racing retries so one logical statement has one durable record."""
    from concurrent.futures import ThreadPoolExecutor

    store = JsonlReviewStatementStore(tmp_path / "reviews.jsonl")

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: _append(store), range(2)))

    assert sorted(created for _record, created in results) == [False, True]
    assert len(store.read()) == 1
    assert results[0][0].digest == results[1][0].digest


def test_concurrent_distinct_statements_preserve_contiguous_chain(
    tmp_path: Path,
) -> None:
    """Serialize independent racing writes without losing either review statement."""
    from concurrent.futures import ThreadPoolExecutor

    store = JsonlReviewStatementStore(tmp_path / "reviews.jsonl")

    def append_index(index: int):
        """Append one uniquely keyed review statement for the race fixture."""
        return _append(
            store,
            idempotency_key=f"review-request-{index}",
            statement=f"statement-{index}",
        )

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(append_index, range(4)))

    records = store.read()
    assert [record.sequence for record in records] == [0, 1, 2, 3]
    assert len({record.digest for record in records}) == 4
