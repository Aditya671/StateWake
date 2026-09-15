"""Chaos Probe."""

from __future__ import annotations

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
import json
import tempfile
import zipfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from statewake.adapters.content_store import ContentAddressedArtifactStore
from statewake.adapters.evidence_ingestion import (
    JsonEvidenceReceiptStore,
    LocalEvidenceIngestionAdapter,
)
from statewake.adapters.reliability_state import (
    JsonlReliabilityStateStore,
    SqliteReliabilityStateStore,
)
from statewake.domain.provenance import ProvenanceGraph, ProvenanceNode
from statewake.domain.reliability_state import ReliabilityStateTransition

NOW = datetime.now(UTC)
results: list[tuple[str, str, str]] = []


def check(name: str, fn: Callable[[], Any]) -> None:
    """Run one chaos probe and record its outcome."""
    try:
        fn()
        results.append((name, "PASS", ""))
    except AssertionError as e:
        results.append((name, "FAIL", str(e)))
    except Exception as e:
        results.append((name, "ERROR", f"{type(e).__name__}: {e}"))


def transition(
    tid: str,
    subject: str,
    frm: str,
    to: str,
    prev: str = "",
    decision: str | None = None,
) -> ReliabilityStateTransition:
    """Build a reliability transition for the chaos probe."""
    if decision is None:
        decision = {
            "reliable": "accept",
            "recovered": "accept",
            "degraded": "review",
            "unreliable": "reject",
        }[to]
    return ReliabilityStateTransition(
        tid,
        subject,
        frm,
        to,
        NOW,
        "chaos",
        "c" * 64,
        "d" * 64,
        decision,
        previous_transition_digest=prev,
    )


def receipt(
    adapter: LocalEvidenceIngestionAdapter, event: str = "e1", content: bytes = b"x"
) -> Any:
    """Create an evidence receipt for a chaos probe."""
    return adapter.ingest_bytes(
        content,
        producer_type="gateway",
        producer_id="p1",
        source_ref="event.json",
        source_event_id=event,
        run_id="r1",
        captured_at=NOW,
    )


def test_content_concurrent() -> None:
    """Exercise the content concurrent chaos invariant."""
    with tempfile.TemporaryDirectory() as d:
        s = ContentAddressedArtifactStore(Path(d))
        with ThreadPoolExecutor(max_workers=32) as ex:
            vals = list(ex.map(lambda _: s.put(b"same"), range(200)))  # type: ignore
        assert len(set(vals)) == 1 and s.get(vals[0]) == b"same"


def test_receipt_concurrent() -> None:
    """Exercise the receipt concurrent chaos invariant."""
    with tempfile.TemporaryDirectory() as d:
        a = LocalEvidenceIngestionAdapter(
            ContentAddressedArtifactStore(Path(d) / "a"),
            JsonEvidenceReceiptStore(Path(d) / "r"),
        )
        with ThreadPoolExecutor(max_workers=32) as ex:
            fut = [ex.submit(receipt, a) for _ in range(100)]
            vals = [f.result() for f in fut]
        assert len({v.receipt_id for v in vals}) == 1


def test_receipt_conflict_concurrent() -> None:
    """Exercise the receipt conflict concurrent chaos invariant."""
    with tempfile.TemporaryDirectory() as d:
        a = LocalEvidenceIngestionAdapter(
            ContentAddressedArtifactStore(Path(d) / "a"),
            JsonEvidenceReceiptStore(Path(d) / "r"),
        )

        def one(i):
            try:
                receipt(a, content=f"x{i}".encode())
                return "ok"
            except ValueError:
                return "conflict"

        with ThreadPoolExecutor(max_workers=32) as ex:
            vals = list(ex.map(one, range(50)))
        assert vals.count("ok") == 1, vals


def test_jsonl_concurrent_tip() -> None:
    """Exercise the jsonl concurrent tip chaos invariant."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "h.jsonl"
        s = JsonlReliabilityStateStore(p)
        t1 = transition("1", "x", "unknown", "reliable")
        # force same stale predecessor concurrently

        def put(t):
            try:
                s.append(t)
                return "ok"
            except ValueError:
                return "stale"

        # both transitions cannot use same predecessor; only t1 should win
        #  if t2 has predecessor mismatch initially? sequential funcs can race
        # but lock serializes
        a = transition("2", "x", "reliable", "degraded", t1.computed_digest)
        b = transition("3", "x", "reliable", "unreliable", t1.computed_digest)
        s.append(t1)
        with ThreadPoolExecutor(max_workers=2) as ex:
            vals = list(ex.map(put, [a, b]))
        assert vals.count("ok") == 1 and vals.count("stale") == 1
        assert len(s.read("x")) == 2


def test_sqlite_concurrent_tip() -> None:
    """Exercise the sqlite concurrent tip chaos invariant."""
    with tempfile.TemporaryDirectory() as d:
        s = SqliteReliabilityStateStore(Path(d) / "h.db")
        t1 = transition("1", "x", "unknown", "reliable")
        s.append(t1)
        a = transition("2", "x", "reliable", "degraded", t1.computed_digest)
        b = transition("3", "x", "reliable", "unreliable", t1.computed_digest)

        def put(t):
            try:
                s.append(t)
                return "ok"
            except ValueError:
                return "stale"

        with ThreadPoolExecutor(max_workers=2) as ex:
            vals = list(ex.map(put, [a, b]))
        assert vals.count("ok") == 1 and vals.count("stale") == 1
        assert len(s.read("x")) == 2


def test_provenance_cycle() -> None:
    """Exercise the provenance cycle chaos invariant."""
    a = ProvenanceNode("a", "x", "a" * 64, "a", ("b",))
    b = ProvenanceNode("b", "x", "b" * 64, "b", ("a",))
    g = ProvenanceGraph((a, b), (("a", "b"), ("b", "a")))
    try:
        g.validate_required_edges()
        raise AssertionError("expected provenance validation to fail")
    except ValueError:
        pass


def test_provenance_missing_edge() -> None:
    """Exercise the provenance missing edge chaos invariant."""
    a = ProvenanceNode("a", "x", "a" * 64, "a")
    b = ProvenanceNode("b", "x", "b" * 64, "b", ("a",))
    g = ProvenanceGraph((a, b), (("b", "a"), ("a", "b")))
    try:
        g.validate_required_edges()
        raise AssertionError("expected provenance validation to fail")
    except ValueError:
        pass


def test_provenance_path_traversal() -> None:
    """Exercise the provenance path traversal chaos invariant."""
    # constructor itself should reject
    try:
        ProvenanceNode("a", "x", "a" * 64, "a", path="../secret")
        raise AssertionError("expected provenance validation to fail")
    except ValueError:
        pass


def test_jsonl_tail_recovery() -> None:
    """Exercise the jsonl tail recovery chaos invariant."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "h"
        p.write_bytes(b'{"broken":')
        assert JsonlReliabilityStateStore(p).read() == []


def test_sqlite_global_read_subject_chain() -> None:
    """Exercise the sqlite global read subject chain chaos invariant."""
    with tempfile.TemporaryDirectory() as d:
        s = SqliteReliabilityStateStore(Path(d) / "h.db")
        a = transition("1", "a", "unknown", "reliable")
        b = transition("2", "b", "unknown", "degraded")
        s.append(a)
        s.append(b)
        assert [x.subject_id for x in s.read("a")] == ["a"]


def test_receipt_tampered_file() -> None:
    """Exercise the receipt tampered file chaos invariant."""
    with tempfile.TemporaryDirectory() as d:
        a = LocalEvidenceIngestionAdapter(
            ContentAddressedArtifactStore(Path(d) / "a"),
            JsonEvidenceReceiptStore(Path(d) / "r"),
        )
        r = receipt(a)
        path = Path(d) / "a" / r.artifact_digest[:2] / r.artifact_digest[2:]
        path.write_bytes(b"evil")
        try:
            a.verify(r)
            raise AssertionError("expected provenance validation to fail")
        except ValueError:
            pass


def test_zip_duplicate_names() -> None:
    """Exercise the zip duplicate names chaos invariant."""
    # Python's ZipFile permits duplicate names; StateWake manifest reader
    # should reject inconsistent artifact mapping via verification.
    from statewake.services.operations_service import verify_bundle

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.zip"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("manifest.json", "{}")
            z.writestr("manifest.json", '{"bundle_id":"x"}')
        try:
            verify_bundle(p)
            raise AssertionError("expected provenance validation to fail")
        except ValueError:
            pass


for n, f in [
    ("content-store concurrency", test_content_concurrent),
    ("receipt idempotency concurrency", test_receipt_concurrent),
    ("receipt conflict concurrency", test_receipt_conflict_concurrent),
    ("jsonl state tip race", test_jsonl_concurrent_tip),
    ("sqlite state tip race", test_sqlite_concurrent_tip),
    ("provenance cycle", test_provenance_cycle),
    ("provenance required edge", test_provenance_missing_edge),
    ("provenance traversal", test_provenance_path_traversal),
    ("jsonl partial tail", test_jsonl_tail_recovery),
    ("sqlite subject read", test_sqlite_global_read_subject_chain),
    ("receipt artifact tamper", test_receipt_tampered_file),
    ("zip duplicate manifest", test_zip_duplicate_names),
]:
    check(n, f)
print(json.dumps(results, indent=2))
print(
    "SUMMARY",
    {s: sum(1 for _, x, _ in results if x == s) for s in ("PASS", "FAIL", "ERROR")},
)
