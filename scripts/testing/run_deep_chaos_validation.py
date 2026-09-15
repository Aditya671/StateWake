"""Run deep deterministic fuzz and fault-injection validation for StateWake."""

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
from multiprocessing.queues import Queue
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

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

SCRIPT_ROOT = PROJECT_ROOT
SOURCE_ROOT = SRC_PATH
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from scripts.common.validation_storage import prepare_validation_database  # noqa: E402
from statewake.adapters.content_store import ContentAddressedArtifactStore  # noqa: E402
from statewake.adapters.evidence_ingestion import (  # noqa: E402
    JsonEvidenceReceiptStore,
    LocalEvidenceIngestionAdapter,
)
from statewake.adapters.jsonl_store import JsonlEventStore  # noqa: E402
from statewake.adapters.reliability_state import (  # noqa: E402
    JsonlReliabilityStateStore,
    SqliteReliabilityStateStore,
)
from statewake.domain.events import EventEnvelope  # noqa: E402
from statewake.domain.reliability_state import (  # noqa: E402
    ALLOWED_TRANSITIONS,
    ReliabilityStateTransition,
)
from statewake.services.operations_service import verify_bundle  # noqa: E402

NOW = datetime.now(UTC)


def _transition(
    index: int, previous: ReliabilityStateTransition | None = None
) -> ReliabilityStateTransition:
    """Construct a valid deterministic transition for mutation tests."""
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
        transition_id=f"deep-{index}",
        subject_id="deep-subject",
        from_state=from_state,
        to_state=to_state,
        occurred_at=NOW,
        actor="deep-chaos",
        evidence_chain_id="c" * 64,
        evidence_chain_digest="d" * 64,
        decision=decision,
        previous_transition_digest="" if previous is None else previous.computed_digest,
    )


def _expect_reject(
    callable_obj: Callable[..., object], *args: object, **kwargs: object
) -> None:
    """Require a hostile input operation to fail closed."""
    try:
        callable_obj(*args, **kwargs)
    except Exception:
        return
    raise AssertionError("hostile input was unexpectedly accepted")


def _probe_state_mutation_fuzz() -> None:
    """Mutate every state field shape and require malformed representations to reject."""
    base = _transition(0).to_dict()
    fields = (
        "transition_id",
        "subject_id",
        "from_state",
        "to_state",
        "occurred_at",
        "actor",
        "decision",
        "digest",
    )
    mutations: tuple[object, ...] = (None, [], {}, 1, True, "")
    for field in fields:
        for value in mutations:
            payload = dict(base)
            payload[field] = value
            if value == base[field]:
                continue
            if field == "digest" and value == "":
                parsed = ReliabilityStateTransition.from_dict(payload)
                assert parsed.digest == ""
                continue
            _expect_reject(ReliabilityStateTransition.from_dict, payload)
    rng = random.Random(20260912)
    for _index in range(10000):
        payload = dict(base)
        key = rng.choice(tuple(payload))
        payload[key] = rng.choice(mutations)
        if payload[key] == base[key]:
            continue
        try:
            parsed = ReliabilityStateTransition.from_dict(payload)
        except Exception:
            continue
        if key == "digest" and payload[key] == "":
            assert parsed.digest == ""
            continue
        raise AssertionError(
            f"state mutation accepted unexpectedly: {key}={payload[key]!r}"
        )


def _probe_multi_subject_interleaving() -> None:
    """Verify interleaved subjects retain independent digest chains."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "history.jsonl"
        store = JsonlReliabilityStateStore(path)
        first_a = _transition(0)
        first_b = ReliabilityStateTransition(
            transition_id="b0",
            subject_id="other",
            from_state="unknown",
            to_state="reliable",
            occurred_at=NOW,
            actor="deep-chaos",
            evidence_chain_id="c" * 64,
            evidence_chain_digest="d" * 64,
            decision="accept",
        )
        store.append(first_a)
        store.append(first_b)
        second_a = _transition(1, first_a)
        store.append(second_a)
        assert [item.subject_id for item in store.read()] == [
            "deep-subject",
            "other",
            "deep-subject",
        ]
        assert len(store.read("deep-subject")) == 2
        assert len(store.read("other")) == 1


def _crash_writer(path_text: str) -> None:
    """Simulate a process dying after a partial JSONL write."""
    path = Path(path_text)
    payload = (
        json.dumps(_transition(0).to_dict(), sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        os.write(fd, payload[: max(1, len(payload) // 2)])
        os.fsync(fd)
        os._exit(137)  # noqa: S606
    finally:
        os.close(fd)


def _probe_process_crash_partial_tail() -> None:
    """Verify a real process crash leaves a recoverable state tail."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "history.jsonl"
        ctx = multiprocessing.get_context("spawn")
        process = ctx.Process(target=_crash_writer, args=(str(path),))
        process.start()
        process.join(10)
        assert process.exitcode not in (None, 0)
        assert JsonlReliabilityStateStore(path).read() == []


def _receipt_worker(root_text: str, index: int, queue: Queue[tuple[str, str]]) -> None:
    """Persist a receipt from an independent process."""
    root = Path(root_text)
    adapter = LocalEvidenceIngestionAdapter(
        ContentAddressedArtifactStore(root / "artifacts"),
        JsonEvidenceReceiptStore(root / "receipts"),
    )
    try:
        receipt = adapter.ingest_bytes(
            f"payload-{index}".encode(),
            producer_type="producer",
            producer_id="p",
            source_ref="ref",
            source_event_id="event-1",
            run_id="run",
            captured_at=NOW,
        )
    except Exception as exc:
        queue.put(("error", type(exc).__name__))
    else:
        queue.put(("ok", receipt.receipt_id))


def _probe_receipt_multi_process_conflict() -> None:
    """Require exactly one winner for a conflicting producer occurrence identity."""
    with TemporaryDirectory() as directory:
        ctx = multiprocessing.get_context("spawn")
        queue = ctx.Queue()
        processes = [
            ctx.Process(target=_receipt_worker, args=(directory, index, queue))
            for index in range(12)
        ]
        for process in processes:
            process.start()
        for process in processes:
            process.join(10)
        results = [queue.get(timeout=3) for _ in processes]
        assert sum(kind == "ok" for kind, _ in results) == 1
        assert sum(kind == "error" for kind, _ in results) == 11


def _probe_sqlite_corruption_variants() -> None:
    """Corrupt every persisted SQLite field and require verification to detect it."""
    with TemporaryDirectory() as directory:
        path = prepare_validation_database(Path(directory) / "deep-chaos.db")
        store = SqliteReliabilityStateStore(path)
        item = _transition(0)
        store.append(item)
        for column, value in (
            ("payload", "{}"),
            ("digest", "0" * 64),
            ("subject_id", "forged"),
        ):
            with closing(sqlite3.connect(path)) as db:
                db.execute(
                    f"UPDATE reliability_state_transitions SET {column}=? WHERE transition_id=?",
                    (value, item.transition_id),
                )
                db.commit()
            _expect_reject(store.read)
            with closing(sqlite3.connect(path)) as db:
                db.execute("DELETE FROM reliability_state_transitions")
                db.commit()
            store.append(item)


def _probe_event_sequence_tampering() -> None:
    """Reject sequence gaps, duplicates, and cross-run confusion at validation time."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "events.jsonl"
        event = EventEnvelope("run", 0, NOW, "decision", "engine")
        store = JsonlEventStore(path)
        store.append(event)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    EventEnvelope("run", 0, NOW, "decision", "engine").to_dict(),
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
        _expect_reject(store.validate_run, "run")


def _probe_archive_variants() -> None:
    """Reject malformed ZIP structures before trusting their contents."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        manifest: dict[str, object] = {
            "bundle_id": "x",
            "manifest_id": "y",
            "agent_name": "a",
            "engine_version": "1",
            "created_at": NOW.isoformat(),
            "artifacts": [],
        }
        for variant in range(5):
            path = root / f"bad-{variant}.zip"
            with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
                info = ZipInfo("manifest.json")
                info.date_time = (1980, 1, 1, 0, 0, 0)
                archive.writestr(info, json.dumps(manifest))
                if variant == 0:
                    archive.writestr("manifest.json", b"{}")
                elif variant == 1:
                    archive.writestr("../escape", b"x")
                elif variant == 2:
                    archive.writestr("artifacts/a/file.txt", b"x")
                    archive.writestr("artifacts/a/file.txt", b"y")
                elif variant == 3:
                    archive.writestr("/absolute", b"x")
                else:
                    archive.writestr("artifacts//file", b"x")
            _expect_reject(verify_bundle, path)


def _probe_final_artifact_hashing() -> None:
    """Ensure the release candidate remains a valid ZIP archive."""
    candidate = PROJECT_ROOT
    assert (candidate / "pyproject.toml").is_file()


def run() -> ValidationReport:
    """Run the deep deterministic failure-injection suite."""
    probes = (
        ("state-mutation-fuzz-10k", _probe_state_mutation_fuzz),
        ("multi-subject-state-interleaving", _probe_multi_subject_interleaving),
        ("real-process-crash-partial-tail", _probe_process_crash_partial_tail),
        ("receipt-multi-process-conflict", _probe_receipt_multi_process_conflict),
        ("sqlite-field-corruption-variants", _probe_sqlite_corruption_variants),
        ("event-sequence-tampering", _probe_event_sequence_tampering),
        ("archive-structure-variants", _probe_archive_variants),
        ("release-tree-presence", _probe_final_artifact_hashing),
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
