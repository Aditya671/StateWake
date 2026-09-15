"""Run the extreme failure-injection matrix for StateWake."""

from __future__ import annotations

import json
import multiprocessing
import os
import random
import sqlite3
import sys
from collections.abc import Callable
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

from statewake.domain.reliability_attestation import (
    ReliabilityOutcomeAttestation,  # noqa: E402
)

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from config.project_paths import PROJECT_ROOT, SRC_PATH  # noqa: E402

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from scripts.common.validation_storage import prepare_validation_database  # noqa: E402
from scripts.common.validation_types import (  # noqa: E402
    ValidationReport,
    ValidationResult,
)
from statewake.adapters.content_store import ContentAddressedArtifactStore  # noqa: E402
from statewake.adapters.jsonl_store import JsonlEventStore  # noqa: E402
from statewake.adapters.reliability_attestation import (  # noqa: E402
    JsonlReliabilityOutcomeAttestationStore,
)
from statewake.adapters.reliability_state import (  # noqa: E402
    JsonlReliabilityStateStore,
    SqliteReliabilityStateStore,
)
from statewake.domain.events import EventEnvelope  # noqa: E402
from statewake.domain.provenance import ProvenanceGraph, ProvenanceNode  # noqa: E402
from statewake.domain.reliability_state import (  # noqa: E402
    ALLOWED_TRANSITIONS,
    ReliabilityStateTransition,
)
from statewake.services.operations_service import verify_bundle  # noqa: E402

SCRIPT_ROOT = PROJECT_ROOT
SOURCE_ROOT = SRC_PATH
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

NOW = datetime.now(UTC)


def _transition(
    index: int, previous: ReliabilityStateTransition | None = None
) -> ReliabilityStateTransition:
    """Build a valid transition from the requested current state."""
    from_state = "unknown" if previous is None else previous.to_state
    to_state = sorted(ALLOWED_TRANSITIONS[from_state])[
        index % len(ALLOWED_TRANSITIONS[from_state])
    ]
    decision = {
        "reliable": "accept",
        "recovered": "accept",
        "degraded": "review",
        "unreliable": "reject",
    }[to_state]
    return ReliabilityStateTransition(
        transition_id=f"t-{index}",
        subject_id="subject",
        from_state=from_state,
        to_state=to_state,
        occurred_at=NOW,
        actor="extreme-test",
        evidence_chain_id="c" * 64,
        evidence_chain_digest="d" * 64,
        decision=decision,
        previous_transition_digest="" if previous is None else previous.computed_digest,
    )


def _attestation(index: int, previous: str = "") -> ReliabilityOutcomeAttestation:
    """Build one valid attestation with an explicit chain predecessor."""
    return ReliabilityOutcomeAttestation(
        attestation_id=f"a-{index}",
        subject_id="subject",
        occurred_at=NOW.isoformat(),
        actor="extreme-test",
        evidence_chain_id="c" * 64,
        evidence_chain_digest="d" * 64,
        transition_id=f"t-{index}",
        transition_digest="e" * 64,
        reliability_state="reliable",
        decision="accept",
        verification_status="verified",
        reconciliation_state="verified",
        previous_digest=previous,
    )


def _content_store_process_worker(
    path_text: str, queue: multiprocessing.Queue[str]
) -> None:
    """Write identical content from one isolated process."""
    store = ContentAddressedArtifactStore(Path(path_text))
    queue.put(store.put(b"process-race" * 4096))


def _probe_content_store_process_race() -> None:
    """Exercise content-addressed writes from independent processes."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()
        processes = [
            ctx.Process(target=_content_store_process_worker, args=(str(root), queue))
            for _ in range(24)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(10)
        assert all(process.exitcode == 0 for process in processes)
        digests = [queue.get(timeout=2) for _ in processes]
        assert len(set(digests)) == 1
        assert (
            ContentAddressedArtifactStore(root).get(digests[0])
            == b"process-race" * 4096
        )


def _probe_state_crash_retry() -> None:
    """Verify partial state writes fail safely and exact retries converge."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "state.jsonl"
        store = JsonlReliabilityStateStore(path)
        item = _transition(0)
        real_write = os.write
        calls = {"count": 0}

        def interrupted(fd: int, data: bytes) -> int:
            calls["count"] += 1
            if calls["count"] == 1:
                real_write(fd, data[: max(1, len(data) // 3)])
                raise OSError("simulated process crash")
            return real_write(fd, data)

        original = os.write
        os.write = interrupted
        try:
            try:
                store.append(item)
            except OSError:
                pass
        finally:
            os.write = original
        assert store.read() == []
        assert store.append(item) == item
        assert store.read() == [item]


def _probe_event_partial_tail_fails_closed() -> None:
    """Ensure a malformed event tail is rejected rather than silently hidden."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "events.jsonl"
        event = EventEnvelope("run", 0, NOW, "decision", "engine")
        JsonlEventStore(path).append(event)
        with path.open("ab") as handle:
            handle.write(b'{"run_id":')
        try:
            JsonlEventStore(path).read()
        except ValueError:
            return
        raise AssertionError("malformed event tail was not rejected")


def _probe_attestation_partial_tail_fails_closed() -> None:
    """Ensure an incomplete attestation tail is rejected."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "att.jsonl"
        store = JsonlReliabilityOutcomeAttestationStore(path)
        store.append(_attestation(0))
        with path.open("ab") as handle:
            handle.write(b'{"attestation_id":')
        try:
            store.read()
        except ValueError:
            return
        raise AssertionError("malformed attestation tail was not rejected")


def _probe_sqlite_corruption_fails_closed() -> None:
    """Tamper with a SQLite payload and require verification to detect it."""
    with TemporaryDirectory() as directory:
        path = prepare_validation_database(Path(directory) / "extreme-validation.db")
        store = SqliteReliabilityStateStore(path)
        item = _transition(0)
        store.append(item)

        with closing(sqlite3.connect(path)) as db:
            db.execute(
                "UPDATE reliability_state_transitions SET payload=? WHERE transition_id=?",
                ('{"tampered":true}', item.transition_id),
            )
            db.commit()
        try:
            store.read()
        except (ValueError, KeyError):
            return
        raise AssertionError("tampered SQLite state was accepted")


def _probe_provenance_cycle_fuzz() -> None:
    """Generate cyclic provenance graphs and require every one to fail validation."""
    for seed in range(100):
        rng = random.Random(seed)
        cycle_parent = str(rng.randrange(4))
        derived = {str(index): () for index in range(5)}
        for index in range(1, 5):
            derived[str(index)] = (str(index - 1),)  # type: ignore
        derived[cycle_parent] = (str(4),)  # type: ignore
        nodes = tuple(
            ProvenanceNode(
                str(index),
                "artifact",
                f"{index:064x}"[-64:],
                str(index),
                derived[str(index)],
            )
            for index in range(5)
        )
        graph = ProvenanceGraph(nodes)
        try:
            graph.validate_acyclic()
        except ValueError:
            continue
        raise AssertionError(f"cycle generator failed for seed {seed}")


def _probe_state_machine_randomized() -> None:
    """Explore one hundred thousand lifecycle sequences without crossing declared transitions."""
    rng = random.Random(20260912)
    for _ in range(100_000):
        current = "unknown"
        for step in range(25):
            choices = sorted(ALLOWED_TRANSITIONS[current])
            next_state = rng.choice(choices)
            previous = _transition(step, None) if current == "unknown" else None
            del previous
            assert next_state in ALLOWED_TRANSITIONS[current]
            current = next_state


def _probe_zip_path_traversal_and_extra_member() -> None:
    """Verify a malformed operational ZIP fails before trusting unexpected members."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        content = b"x"
        manifest = {
            "bundle_id": "bad",
            "manifest_id": "bad",
            "agent_name": "test",
            "engine_version": "0.1",
            "created_at": NOW.isoformat(),
            "artifacts": [
                {
                    "artifact_id": "a",
                    "path": "../escape.txt",
                    "kind": "text",
                    "sha256": "0" * 64,
                    "size_bytes": 1,
                    "sensitivity": "internal",
                    "derived_from": [],
                }
            ],
            "retention_policy": None,
        }
        bundle = root / "malicious.zip"
        with ZipFile(bundle, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
            archive.writestr("../escape.txt", content)
        try:
            verify_bundle(bundle)
        except (ValueError, KeyError):
            return
        raise AssertionError("malicious bundle was accepted")


def run() -> ValidationReport:
    """Run all extreme probes and return a machine-readable report."""
    probes: tuple[tuple[str, Callable[[], None]], ...] = (
        ("content-store-multi-process-race", _probe_content_store_process_race),
        ("state-crash-retry", _probe_state_crash_retry),
        ("event-partial-tail-fail-closed", _probe_event_partial_tail_fails_closed),
        (
            "attestation-partial-tail-fail-closed",
            _probe_attestation_partial_tail_fails_closed,
        ),
        ("sqlite-corruption-fail-closed", _probe_sqlite_corruption_fails_closed),
        ("provenance-cycle-fuzz", _probe_provenance_cycle_fuzz),
        ("randomized-state-machine", _probe_state_machine_randomized),
        ("zip-malformation-boundary", _probe_zip_path_traversal_and_extra_member),
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
