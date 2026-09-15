"""Execute high-stress, adversarial StateWake reliability-boundary probes."""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
from __future__ import annotations

import json
import sys
import tempfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from config.project_paths import PROJECT_ROOT, SRC_PATH  # noqa: E402

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from scripts.common.validation_types import (  # noqa: E402
    ValidationReport,
    ValidationResult,
)
from statewake.adapters.content_store import ContentAddressedArtifactStore  # noqa: E402
from statewake.adapters.evidence_ingestion import (  # noqa: E402
    JsonEvidenceReceiptStore,
    LocalEvidenceIngestionAdapter,
)
from statewake.adapters.reliability_state import (  # noqa: E402
    JsonlReliabilityStateStore,
    SqliteReliabilityStateStore,
)
from statewake.domain.provenance import ProvenanceGraph, ProvenanceNode  # noqa: E402
from statewake.domain.reliability_state import ReliabilityStateTransition  # noqa: E402

SCRIPT_ROOT = PROJECT_ROOT
SOURCE_ROOT = SRC_PATH

NOW: Final = datetime.now(UTC)


def _transition(
    transition_id: str,
    subject_id: str,
    from_state: str,
    to_state: str,
    previous: str = "",
) -> ReliabilityStateTransition:
    """Build one deterministic transition for concurrency probes."""
    decision = {
        "reliable": "accept",
        "recovered": "accept",
        "degraded": "review",
        "unreliable": "reject",
    }[to_state]
    return ReliabilityStateTransition(
        transition_id=transition_id,
        subject_id=subject_id,
        from_state=from_state,
        to_state=to_state,
        occurred_at=NOW,
        actor="chaos-test",
        evidence_chain_id="c" * 64,
        evidence_chain_digest="d" * 64,
        decision=decision,
        previous_transition_digest=previous,
    )


def _probe_content_store_concurrency() -> None:
    """Verify content-addressed writes remain idempotent under contention."""
    with tempfile.TemporaryDirectory() as directory:
        store = ContentAddressedArtifactStore(Path(directory))

        def put_same_content(_: int) -> str:
            return store.put(b"same-content")

        with ThreadPoolExecutor(max_workers=32) as executor:
            digests = list(executor.map(put_same_content, range(250)))
        assert len(set(digests)) == 1
        assert store.get(digests[0]) == b"same-content"


def _probe_receipt_concurrency() -> None:
    """Verify identical producer events converge to one receipt under contention."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        adapter = LocalEvidenceIngestionAdapter(
            ContentAddressedArtifactStore(root / "artifacts"),
            JsonEvidenceReceiptStore(root / "receipts"),
        )

        def ingest(_: int):
            return adapter.ingest_bytes(
                b"event",
                producer_type="payment-gateway",
                producer_id="gateway",
                source_ref="producer://gateway/event-1",
                source_event_id="event-1",
                run_id="run-1",
                captured_at=NOW,
            )

        with ThreadPoolExecutor(max_workers=32) as executor:
            receipts = list(executor.map(ingest, range(100)))
        assert len({item.receipt_id for item in receipts}) == 1


def _probe_receipt_conflict() -> None:
    """Verify concurrent conflicting payloads cannot reuse one producer occurrence identity."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        adapter = LocalEvidenceIngestionAdapter(
            ContentAddressedArtifactStore(root / "artifacts"),
            JsonEvidenceReceiptStore(root / "receipts"),
        )

        def ingest(index: int) -> str:
            try:
                adapter.ingest_bytes(
                    f"event-{index}".encode(),
                    producer_type="payment-gateway",
                    producer_id="gateway",
                    source_ref="producer://gateway/event-1",
                    source_event_id="event-1",
                    run_id="run-1",
                    captured_at=NOW,
                )
            except ValueError:
                return "conflict"
            return "accepted"

        with ThreadPoolExecutor(max_workers=32) as executor:
            outcomes = list(executor.map(ingest, range(100)))
        assert outcomes.count("accepted") == 1
        assert outcomes.count("conflict") == 99


def _probe_state_tip_race(store_factory: Callable[[Path], Any], filename: str) -> None:
    """Verify competing transitions from one state tip cannot both commit."""
    with tempfile.TemporaryDirectory() as directory:
        store = store_factory(Path(directory) / filename)
        first = _transition("first", "subject", "unknown", "reliable")
        store.append(first)
        a = _transition("a", "subject", "reliable", "degraded", first.computed_digest)
        b = _transition("b", "subject", "reliable", "unreliable", first.computed_digest)

        def append(item: ReliabilityStateTransition) -> str:
            try:
                store.append(item)
            except ValueError:
                return "stale"
            return "accepted"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(append, (a, b)))
        assert outcomes.count("accepted") == 1
        assert outcomes.count("stale") == 1
        assert len(store.read("subject")) == 2


def _probe_provenance_attacks() -> None:
    """Verify cyclic and missing-edge provenance graphs fail closed."""
    cyclic = ProvenanceGraph(
        (
            ProvenanceNode("a", "artifact", "a" * 64, "a", ("b",)),
            ProvenanceNode("b", "artifact", "b" * 64, "b", ("a",)),
        ),
        (("a", "b"), ("b", "a")),
    )
    try:
        cyclic.validate_required_edges()
    except ValueError:
        pass
    else:
        raise AssertionError("cyclic provenance graph was accepted")

    missing = ProvenanceGraph(
        (
            ProvenanceNode("a", "artifact", "a" * 64, "a"),
            ProvenanceNode("b", "artifact", "b" * 64, "b", ("a",)),
        ),
        (("a", "b"),),
    )
    try:
        missing.validate_required_edges()
    except ValueError:
        pass
    else:
        raise AssertionError("missing provenance edge was accepted")


def _probe_predecessor_binding(
    store_factory: Callable[[Path], Any], filename: str
) -> None:
    """Verify a hash-linked transition cannot lie about its predecessor state."""
    with tempfile.TemporaryDirectory() as directory:
        store = store_factory(Path(directory) / filename)
        first = _transition("first", "subject", "unknown", "reliable")
        invalid = _transition(
            "invalid", "subject", "unknown", "degraded", first.computed_digest
        )
        store.append(first)
        try:
            store.append(invalid)
        except ValueError as exc:
            assert "predecessor mismatch" in str(exc)
        else:
            raise AssertionError("state store accepted a mismatched predecessor state")


def run() -> ValidationReport:
    """Run all chaos probes and return a machine-readable report."""
    probes: tuple[tuple[str, Callable[[], None]], ...] = (
        ("content-addressed-write-concurrency", _probe_content_store_concurrency),
        ("receipt-idempotency-concurrency", _probe_receipt_concurrency),
        ("receipt-conflict-concurrency", _probe_receipt_conflict),
        (
            "jsonl-state-tip-race",
            lambda: _probe_state_tip_race(JsonlReliabilityStateStore, "history.jsonl"),
        ),
        (
            "sqlite-state-tip-race",
            lambda: _probe_state_tip_race(SqliteReliabilityStateStore, "history.db"),
        ),
        ("provenance-cycle-and-edge-attacks", _probe_provenance_attacks),
        (
            "jsonl-predecessor-binding",
            lambda: _probe_predecessor_binding(
                JsonlReliabilityStateStore, "history.jsonl"
            ),
        ),
        (
            "sqlite-predecessor-binding",
            lambda: _probe_predecessor_binding(
                SqliteReliabilityStateStore, "history.db"
            ),
        ),
    )
    results: list[ValidationResult] = []
    for name, probe in probes:
        try:
            probe()
        except Exception as exc:
            results.append(
                {
                    "probe": name,
                    "passed": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        else:
            results.append({"probe": name, "passed": True})
    return {
        "passed": all(item["passed"] for item in results),
        "probe_count": len(results),
        "results": results,
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
