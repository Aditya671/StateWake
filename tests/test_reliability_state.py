"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
import json
import tempfile
import threading
import unittest
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from statewake.adapters.reliability_state import JsonlReliabilityStateStore
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.domain.reliability_state import ReliabilityStateTransition
from statewake.services.reliability_state_service import (
    current_reliability_state,
    transition_reliability_state,
)


class ReliabilityStateLifecycleTests(unittest.TestCase):
    """Provide regression coverage for the ReliabilityStateLifecycleTests behavior."""

    def _chain(
        self, root: Path, *, state: str, decision: str, recovery: bool = False
    ) -> ReliabilityEvidenceChain:
        """Verify the `_chain` behavior and its expected invariants."""

        def write(name: str, payload: object) -> Path:
            """Verify the `write` behavior and its expected invariants."""
            path = root / name
            path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            return path

        run = write(f"run-{state}.json", {"run": state})
        system_state = write(f"state-{state}.json", {"state": state})
        evidence = write(f"evidence-{state}.json", {"evidence": state})
        provenance = write(f"provenance-{state}.json", {"provenance": state})
        integrity = write(f"integrity-{state}.json", {"verified": decision != "reject"})
        write(
            f"reconciliation-{state}.json",
            {"state": "recovered" if recovery else "verified"},
        )
        recovery_path = (
            write(f"recovery-{state}.json", {"recovery": state}) if recovery else None
        )
        return ReliabilityEvidenceChain(
            chain_id=f"chain-{state}",
            run=EvidenceReference("run", run.name, "0" * 64),
            state=EvidenceReference("state", system_state.name, "1" * 64),
            evidence=(EvidenceReference("evidence", evidence.name, "2" * 64),),
            provenance=EvidenceReference("provenance", provenance.name, "3" * 64),
            integrity=EvidenceReference("integrity", integrity.name, "4" * 64),
            verification_status="verified",
            reliability_state=state,
            reconciliation_state="recovered" if recovery else "verified",
            recovery_ref=None
            if recovery_path is None
            else EvidenceReference("recovery", recovery_path.name, "5" * 64),
            decision=decision,
            decision_rationale=(f"transition to {state}",),
        )

    def test_unknown_to_reliable_and_current_state(self):
        """Verify the `test_unknown_to_reliable_and_current_state` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = JsonlReliabilityStateStore(root / "history.jsonl")
            chain = self._chain(root, state="reliable", decision="accept")
            transition = transition_reliability_state(
                "agent-a", chain, store=store, actor="engine"
            )
            self.assertEqual(transition.from_state, "unknown")
            snapshot = current_reliability_state("agent-a", store=store)
            self.assertEqual(snapshot.state, "reliable")

    def test_exact_retry_is_idempotent(self):
        """Verify the `test_exact_retry_is_idempotent` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = JsonlReliabilityStateStore(root / "history.jsonl")
            chain = self._chain(root, state="reliable", decision="accept")
            when = datetime(2026, 9, 11, 0, 0, tzinfo=UTC)
            first = transition_reliability_state(
                "agent-a", chain, store=store, actor="engine", occurred_at=when
            )
            second = transition_reliability_state(
                "agent-a", chain, store=store, actor="engine", occurred_at=when
            )
            self.assertEqual(first, second)
            self.assertEqual(len(store.read("agent-a")), 1)

    def test_invalid_transition_fails(self):
        """Verify the `test_invalid_transition_fails` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = JsonlReliabilityStateStore(root / "history.jsonl")
            transition_reliability_state(
                "agent-a",
                self._chain(root, state="reliable", decision="accept"),
                store=store,
                actor="engine",
            )
            with self.assertRaisesRegex(
                ValueError, "invalid reliability-state transition"
            ):
                transition_reliability_state(
                    "agent-a",
                    self._chain(
                        root, state="recovered", decision="accept", recovery=True
                    ),
                    store=store,
                    actor="engine",
                )

    def test_recovered_requires_unreliable_predecessor_and_recovery_evidence(self):
        """Verify the `test_recovered_requires_unreliable_predecessor_and_recovery_evidence` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = JsonlReliabilityStateStore(root / "history.jsonl")
            transition_reliability_state(
                "agent-a",
                self._chain(root, state="unreliable", decision="reject"),
                store=store,
                actor="engine",
            )
            recovered = transition_reliability_state(
                "agent-a",
                self._chain(root, state="recovered", decision="accept", recovery=True),
                store=store,
                actor="engine",
            )
            self.assertEqual(recovered.from_state, "unreliable")

    def test_stale_writer_is_rejected(self):
        """Verify the `test_stale_writer_is_rejected` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = JsonlReliabilityStateStore(root / "history.jsonl")
            transition_reliability_state(
                "agent-a",
                self._chain(root, state="reliable", decision="accept"),
                store=store,
                actor="engine",
            )
            second = self._chain(root, state="degraded", decision="review")
            stale = ReliabilityStateTransition(
                transition_id="stale",
                subject_id="agent-a",
                from_state="reliable",
                to_state="degraded",
                occurred_at=datetime.now(UTC),
                actor="engine",
                evidence_chain_id=second.chain_id,
                evidence_chain_digest=second.digest(),
                decision="review",
                previous_transition_digest="0" * 64,
            )
            with self.assertRaisesRegex(ValueError, "stale reliability-state tip"):
                store.append(stale)

    def test_concurrent_writers_are_serialized(self):
        """Verify the `test_concurrent_writers_are_serialized` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = JsonlReliabilityStateStore(
                root / "history.jsonl", lock_timeout_seconds=2
            )
            errors = []
            when = datetime(2026, 9, 11, 0, 0, tzinfo=UTC)
            chain = self._chain(root, state="reliable", decision="accept")

            def worker():
                """Verify the `worker` behavior and its expected invariants."""
                try:
                    transition_reliability_state(
                        "agent-a", chain, store=store, actor="engine", occurred_at=when
                    )
                except Exception as exc:  # pragma: no cover - assertion below reports any unexpected race/error
                    errors.append(exc)

            threads = [threading.Thread(target=worker) for _ in range(6)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            self.assertEqual(len(store.read("agent-a")), 1)

    def test_tampered_history_is_detected(self):
        """Verify the `test_tampered_history_is_detected` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = JsonlReliabilityStateStore(root / "history.jsonl")
            transition_reliability_state(
                "agent-a",
                self._chain(root, state="reliable", decision="accept"),
                store=store,
                actor="engine",
            )
            path = root / "history.jsonl"
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["actor"] = "tampered"
            path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                store.read("agent-a")


if __name__ == "__main__":
    unittest.main()


def test_partial_final_record_is_recovered(tmp_path):
    path = tmp_path / "state.jsonl"
    store = JsonlReliabilityStateStore(path)
    transition = ReliabilityStateTransition(
        transition_id="t1",
        subject_id="s1",
        from_state="unknown",
        to_state="reliable",
        occurred_at=datetime.now(UTC),
        actor="tester",
        evidence_chain_id="chain-1",
        evidence_chain_digest="0" * 64,
        decision="accept",
        rationale=("verified",),
    )
    store.append(transition)
    with path.open("ab") as handle:
        handle.write(b'{"partial":')
    assert store.read("s1")[0].transition_id == "t1"
    assert path.read_bytes().endswith(b"\n")


def test_sqlite_state_store_initialization_creates_database_idempotently(tmp_path):
    """Verify first-use SQLite initialization creates a reusable local database."""
    from statewake.adapters.reliability_state import SqliteReliabilityStateStore

    path = tmp_path / "data" / "state.db"
    store = SqliteReliabilityStateStore(path)
    assert not path.exists()
    store.initialize()
    assert path.exists()
    store.initialize()
    assert store.read() == []


def test_sqlite_state_store_is_transactional_reference_adapter(tmp_path):
    from statewake.adapters.reliability_state import SqliteReliabilityStateStore

    path = tmp_path / "state.db"
    store = SqliteReliabilityStateStore(path)
    transition = ReliabilityStateTransition(
        transition_id="sqlite-t1",
        subject_id="sqlite-s1",
        from_state="unknown",
        to_state="reliable",
        occurred_at=datetime.now(UTC),
        actor="tester",
        evidence_chain_id="chain-1",
        evidence_chain_digest="0" * 64,
        decision="accept",
        rationale=("verified",),
    )
    assert store.append(transition) == transition
    assert store.read("sqlite-s1") == [transition]


def test_interrupted_append_leaves_only_a_recoverable_partial_tail(
    tmp_path, monkeypatch
):
    import os

    from statewake.domain.reliability_state import ReliabilityStateTransition

    path = tmp_path / "state.jsonl"
    store = JsonlReliabilityStateStore(path)
    transition = ReliabilityStateTransition(
        transition_id="fault-t1",
        subject_id="fault-s1",
        from_state="unknown",
        to_state="reliable",
        occurred_at=datetime.now(UTC),
        actor="tester",
        evidence_chain_id="chain-1",
        evidence_chain_digest="0" * 64,
        decision="accept",
        rationale=("verified",),
    )
    real_write = os.write
    calls = {"n": 0}

    def interrupted_write(fd, data):
        calls["n"] += 1
        if calls["n"] == 1:
            prefix = max(1, len(data) // 2)
            real_write(fd, data[:prefix])
            raise OSError("synthetic power-loss interruption")
        return real_write(fd, data)

    monkeypatch.setattr(os, "write", interrupted_write)
    with pytest.raises(OSError, match="synthetic power-loss interruption"):
        store.append(transition)
    assert path.exists()
    assert store.read("fault-s1") == []
    assert path.read_bytes() == b""


def _hold_reliability_state_lock(lock_path: str, signal) -> None:
    store = JsonlReliabilityStateStore(Path(lock_path), lock_timeout_seconds=10)
    with store._lock():  # type: ignore
        signal.set()
        import time

        time.sleep(30)


def test_cross_process_lock_owner_recovery_after_termination(tmp_path):
    import multiprocessing

    path = tmp_path / "state.jsonl"
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    process = context.Process(
        target=_hold_reliability_state_lock, args=(str(path), ready)
    )
    process.start()
    assert ready.wait(5)
    process.terminate()
    process.join(5)
    assert process.exitcode is not None

    store = JsonlReliabilityStateStore(path, lock_timeout_seconds=1)
    transition = ReliabilityStateTransition(
        transition_id="owner-t1",
        subject_id="owner-s1",
        from_state="unknown",
        to_state="reliable",
        occurred_at=datetime.now(UTC),
        actor="tester",
        evidence_chain_id="chain-1",
        evidence_chain_digest="0" * 64,
        decision="accept",
        rationale=("verified",),
    )
    assert store.append(transition) == transition


def test_jsonl_read_acquires_exclusive_lock_before_recovery(tmp_path):
    """Verify readers cannot recover partial state concurrently with a writer."""
    path = tmp_path / "state.jsonl"
    path.write_bytes(b'{"partial":')
    store = JsonlReliabilityStateStore(path)
    lock_held = threading.Event()
    release_lock = threading.Event()
    read_finished = threading.Event()

    def hold_lock() -> None:
        with store._lock():  # type: ignore
            lock_held.set()
            release_lock.wait(2)

    def read_state() -> None:
        store.read()
        read_finished.set()

    holder = threading.Thread(target=hold_lock)
    reader = threading.Thread(target=read_state)
    holder.start()
    assert lock_held.wait(1)
    reader.start()
    assert not read_finished.wait(0.1)
    release_lock.set()
    holder.join(2)
    reader.join(2)
    assert read_finished.is_set()
    assert path.read_bytes() == b""


def test_sqlite_read_rejects_reordered_transition_chain(tmp_path):
    """Verify SQLite reads reject validly serialized transitions in broken order."""
    from statewake.adapters.reliability_state import SqliteReliabilityStateStore

    path = tmp_path / "state.db"
    store = SqliteReliabilityStateStore(path)
    first = ReliabilityStateTransition(
        transition_id="sqlite-chain-1",
        subject_id="sqlite-chain",
        from_state="unknown",
        to_state="reliable",
        occurred_at=datetime(2026, 9, 11, tzinfo=UTC),
        actor="tester",
        evidence_chain_id="chain-1",
        evidence_chain_digest="0" * 64,
        decision="accept",
        rationale=("first",),
    )
    second = ReliabilityStateTransition(
        transition_id="sqlite-chain-2",
        subject_id="sqlite-chain",
        from_state="reliable",
        to_state="degraded",
        occurred_at=datetime(2026, 9, 12, tzinfo=UTC),
        actor="tester",
        evidence_chain_id="chain-2",
        evidence_chain_digest="1" * 64,
        decision="review",
        rationale=("second",),
        previous_transition_digest=first.computed_digest,
    )
    store.append(first)
    store.append(second)

    import sqlite3

    with closing(sqlite3.connect(path)) as database:
        database.execute(
            "UPDATE reliability_state_transitions SET subject_id=?, digest=?, payload=? WHERE sequence=?",
            (
                second.subject_id,
                second.computed_digest,
                json.dumps(second.to_dict(), sort_keys=True, separators=(",", ":")),
                1,
            ),
        )
        database.execute(
            "UPDATE reliability_state_transitions SET subject_id=?, digest=?, payload=? WHERE sequence=?",
            (
                first.subject_id,
                first.computed_digest,
                json.dumps(first.to_dict(), sort_keys=True, separators=(",", ":")),
                2,
            ),
        )
        database.commit()

    with pytest.raises(ValueError, match="previous transition digest"):
        store.read("sqlite-chain")


def test_state_store_rejects_from_state_mismatch() -> None:
    """Reject a transition whose declared predecessor state disagrees with history."""
    from datetime import datetime
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from statewake.adapters.reliability_state import (
        JsonlReliabilityStateStore,
        SqliteReliabilityStateStore,
    )
    from statewake.domain.reliability_state import ReliabilityStateTransition

    when = datetime(2026, 9, 12, tzinfo=UTC)
    first = ReliabilityStateTransition(
        transition_id="first",
        subject_id="subject",
        from_state="unknown",
        to_state="reliable",
        occurred_at=when,
        actor="test",
        evidence_chain_id="a" * 64,
        evidence_chain_digest="b" * 64,
        decision="accept",
    )
    invalid = ReliabilityStateTransition(
        transition_id="invalid",
        subject_id="subject",
        from_state="unknown",
        to_state="degraded",
        occurred_at=when,
        actor="test",
        evidence_chain_id="a" * 64,
        evidence_chain_digest="b" * 64,
        decision="review",
        previous_transition_digest=first.computed_digest,
    )
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for store in (
            JsonlReliabilityStateStore(root / "history.jsonl"),
            SqliteReliabilityStateStore(root / "history.db"),
        ):
            store.append(first)
            try:
                store.append(invalid)
            except ValueError as exc:
                assert "predecessor mismatch" in str(exc)
            else:
                raise AssertionError(
                    "state store accepted a mismatched predecessor state"
                )
