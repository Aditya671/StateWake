"""Hardening regression tests for persistence and hostile input boundaries."""

from __future__ import annotations

import json
import multiprocessing
import unittest
from datetime import UTC, datetime
from pathlib import Path

import pytest

from statewake.adapters.jsonl_store import JsonlEventStore
from statewake.adapters.reliability_attestation import (
    JsonlReliabilityOutcomeAttestationStore,
)
from statewake.adapters.reliability_state import JsonlReliabilityStateStore
from statewake.domain.attestation_trust import SignedAttestationTrustState
from statewake.domain.events import EventEnvelope
from statewake.domain.reliability_attestation import ReliabilityOutcomeAttestation
from statewake.domain.reliability_comparison import ReliabilityBehavioralComparison
from statewake.domain.reliability_lineage import ReliabilityLineageClosure
from statewake.domain.reliability_proof_bundle import ReliabilityProofBundleDescriptor
from statewake.domain.reliability_state import ReliabilityStateTransition

NOW = datetime(2026, 9, 12, tzinfo=UTC)


def _transition(
    transition_id: str, subject_id: str = "subject"
) -> ReliabilityStateTransition:
    """Build one minimal valid reliability transition."""
    return ReliabilityStateTransition(
        transition_id=transition_id,
        subject_id=subject_id,
        from_state="unknown",
        to_state="reliable",
        occurred_at=NOW,
        actor="test",
        evidence_chain_id="chain",
        evidence_chain_digest="a" * 64,
        decision="accept",
    )


def _attestation(attestation_id: str) -> ReliabilityOutcomeAttestation:
    """Build one minimal valid reliability attestation."""
    return ReliabilityOutcomeAttestation(
        attestation_id=attestation_id,
        subject_id="subject",
        occurred_at=NOW.isoformat(),
        actor="test",
        evidence_chain_id="chain",
        evidence_chain_digest="a" * 64,
        transition_id=attestation_id,
        transition_digest="b" * 64,
        reliability_state="reliable",
        decision="accept",
        verification_status="verified",
        reconciliation_state="verified",
    )


def test_state_store_keeps_complete_final_record_without_newline(
    tmp_path: Path,
) -> None:
    """Do not mistake a complete JSONL record without a newline for a partial crash tail."""
    path = tmp_path / "state.jsonl"
    transition = _transition("t1")
    path.write_text(
        json.dumps(transition.to_dict(), sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    records = JsonlReliabilityStateStore(path).read()

    assert records == [transition]
    assert path.read_text(encoding="utf-8") != ""


def test_event_store_round_trip_preserves_binary_atomic_append(tmp_path: Path) -> None:
    """Persist one event as one complete durable JSONL record."""
    path = tmp_path / "events.jsonl"
    store = JsonlEventStore(path)
    event = EventEnvelope(
        run_id="run",
        sequence=0,
        occurred_at=NOW,
        event_type="decision",
        actor="engine",
        metadata={"value": "x" * 10000},
    )

    store.append(event)

    assert store.read() == [event]


def test_event_deserialization_rejects_numeric_coercion() -> None:
    """Reject floats and booleans masquerading as event sequence integers."""
    payload = EventEnvelope(
        run_id="run",
        sequence=1,
        occurred_at=NOW,
        event_type="decision",
        actor="engine",
    ).to_dict()
    payload["sequence"] = 1.5
    with pytest.raises((TypeError, ValueError)):
        EventEnvelope.from_dict(payload)
    payload["sequence"] = True
    with pytest.raises((TypeError, ValueError)):
        EventEnvelope.from_dict(payload)


def _event_process(
    path_text: str, index: int, queue: multiprocessing.Queue[str]
) -> None:
    """Append one distinct event from a separate process."""
    store = JsonlEventStore(Path(path_text), lock_timeout_seconds=10.0)
    store.append(
        EventEnvelope(
            run_id="run",
            sequence=index,
            occurred_at=NOW,
            event_type="decision",
            actor="engine",
            metadata={"index": str(index), "payload": "z" * 2048},
        )
    )
    queue.put("ok")


def _attestation_process(
    path_text: str, index: int, queue: multiprocessing.Queue[str]
) -> None:
    """Attempt one attestation append from a separate process."""
    store = JsonlReliabilityOutcomeAttestationStore(
        Path(path_text), lock_timeout_seconds=10.0
    )
    item = _attestation(f"a-{index}")
    try:
        store.append(item)
    except ValueError:
        queue.put("rejected")
    else:
        queue.put("ok")


def test_event_store_is_safe_against_multi_process_record_interleaving(
    tmp_path: Path,
) -> None:
    """Ensure separate processes cannot interleave JSONL event records."""
    ctx = multiprocessing.get_context("spawn")
    path = tmp_path / "events.jsonl"
    queue = ctx.Queue()
    processes = [
        ctx.Process(target=_event_process, args=(str(path), index, queue))
        for index in range(40)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(10)
    assert all(process.exitcode == 0 for process in processes)
    assert [queue.get(timeout=2) for _ in processes].count("ok") == len(processes)

    events = JsonlEventStore(path).read("run")
    assert len(events) == 40
    assert {event.sequence for event in events} == set(range(40))


def test_attestation_store_is_safe_against_multi_process_chain_races(
    tmp_path: Path,
) -> None:
    """Allow exactly one initial attestation and keep the remaining writers stale."""
    ctx = multiprocessing.get_context("spawn")
    path = tmp_path / "attestations.jsonl"
    queue = ctx.Queue()
    processes = [
        ctx.Process(target=_attestation_process, args=(str(path), index, queue))
        for index in range(20)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(10)
    assert all(process.exitcode == 0 for process in processes)
    outcomes = [queue.get(timeout=2) for _ in processes]
    assert outcomes.count("ok") == 1
    assert outcomes.count("rejected") == 19
    assert len(JsonlReliabilityOutcomeAttestationStore(path).read()) == 1


def test_partial_jsonl_state_tail_is_recovered_but_not_valid_record(
    tmp_path: Path,
) -> None:
    """Keep valid history while removing a demonstrably incomplete final JSON object."""
    path = tmp_path / "state.jsonl"
    store = JsonlReliabilityStateStore(path)
    store.append(_transition("t1"))
    with path.open("ab") as handle:
        handle.write(b'{"transition_id":')

    assert store.read("subject")[0].transition_id == "t1"
    assert path.read_bytes().endswith(b"\n")


class TestSerializedListBoundaries(unittest.TestCase):
    """Verify malformed serialized collection members fail closed."""

    def test_trust_state_rejects_non_object_anchor(self) -> None:
        """Reject malformed attestation-trust anchor members."""
        payload = {
            "authority_key_id": "authority",
            "version": 1,
            "issued_at": "now",
            "anchors": [1],
            "signature": "sig",
        }
        with self.assertRaises(ValueError):
            SignedAttestationTrustState.from_dict(payload)  # type: ignore

    def test_lineage_rejects_non_object_binding(self) -> None:
        """Reject malformed lineage binding members."""
        payload = {
            "format_version": "1",
            "provenance_graph_digest": "a" * 64,
            "bindings": [1],
            "reachable_roles": ["run"],
            "digest": "b" * 64,
        }
        with self.assertRaises(ValueError):
            ReliabilityLineageClosure.from_dict(payload)  # type: ignore

    def test_comparison_rejects_non_object_input(self) -> None:
        """Reject malformed behavioral comparison members."""
        payload = {  # type: ignore
            "comparison_id": "x",
            "before": [1],
            "after": [1],
            "diff": {},
            "significance": "none",
        }
        with self.assertRaises(ValueError):
            ReliabilityBehavioralComparison.from_dict(payload)  # type: ignore

    def test_proof_descriptor_rejects_non_object_source(self) -> None:
        """Reject malformed proof-source members."""
        payload = {
            "format_version": "1",
            "bundle_type": "reliability-proof",
            "subject_id": "s",
            "attestation_artifact_id": "a",
            "evidence_chain_artifact_id": "b",
            "state_history_artifact_id": "c",
            "verification_report_artifact_id": "d",
            "attestation_id": "a",
            "attestation_digest": "e" * 64,
            "evidence_chain_id": "e",
            "evidence_chain_digest": "f" * 64,
            "transition_id": "t",
            "transition_digest": "g" * 64,
            "reliability_state": "reliable",
            "decision": "accept",
            "verification_report_digest": "h" * 64,
            "sources": [1],
        }
        with self.assertRaises(ValueError):
            ReliabilityProofBundleDescriptor.from_dict(payload)  # type: ignore


def test_numeric_json_boundaries_reject_booleans() -> None:
    """Reject JSON booleans where persisted integer contracts require integers."""
    from statewake.domain.evidence_admission import ExternalEvidenceAdmission
    from statewake.domain.evidence_receipt import ExternalEvidenceReceipt

    admission = {
        "receipt_id": "r",
        "receipt_digest": "a" * 64,
        "artifact_digest": "b" * 64,
        "artifact_size": True,
        "producer_type": "p",
        "producer_id": "i",
        "source_event_id": None,
        "run_id": None,
        "evidence_reference": {
            "kind": "evidence",
            "identity": "e",
            "digest": "b" * 64,
            "receipt_ref": {"kind": "receipt", "identity": "r", "digest": "a" * 64},
        },
    }
    with pytest.raises(ValueError, match="artifact_size must be a JSON integer"):
        ExternalEvidenceAdmission.from_dict(admission)  # type: ignore

    receipt = {
        "producer_type": "p",
        "producer_id": "i",
        "artifact_digest": "b" * 64,
        "artifact_size": True,
        "captured_at": "2026-09-12T00:00:00+00:00",
        "source_ref": "ref",
    }
    with pytest.raises(ValueError, match="artifact_size must be a JSON integer"):
        ExternalEvidenceReceipt.from_dict(receipt)
