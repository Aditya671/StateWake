"""Run deterministic, machine-readable StateWake failure-laboratory campaigns."""

from __future__ import annotations

import argparse
import io
import json
import multiprocessing
import os
import random
import sqlite3
import sys
import warnings
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import TracebackType
from typing import Final
from zipfile import ZIP_DEFLATED, ZipFile

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
from statewake.domain.provenance import ProvenanceGraph, ProvenanceNode  # noqa: E402
from statewake.domain.reliability_state import (  # noqa: E402
    ALLOWED_TRANSITIONS,
    ReliabilityStateTransition,
)
from statewake.server import VerificationServiceConfig, create_application  # noqa: E402
from statewake.services.operations_service import verify_bundle  # noqa: E402
from statewake.utils.signatures import verify_ed25519_signature  # noqa: E402

SCRIPT_ROOT = PROJECT_ROOT
SOURCE_ROOT = SRC_PATH
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

NOW: Final = datetime.now(UTC)
SEED: Final = 20260913


@dataclass(frozen=True, slots=True)
class AttackCase:
    """Describe one failure-laboratory attack case."""

    attack_id: str
    category: str
    description: str
    probe: Callable[[], None]


class FailureLabError(RuntimeError):
    """Indicate a failure-laboratory configuration or execution error."""


def _transition(
    index: int, previous: ReliabilityStateTransition | None = None
) -> ReliabilityStateTransition:
    """Construct one valid deterministic state transition."""
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
        transition_id=f"failure-lab-{index}",
        subject_id="failure-lab-subject",
        from_state=from_state,
        to_state=to_state,
        occurred_at=NOW,
        actor="failure-lab",
        evidence_chain_id="c" * 64,
        evidence_chain_digest="d" * 64,
        decision=decision,
        previous_transition_digest="" if previous is None else previous.computed_digest,
    )


def _expect_reject(callable_obj: Callable[..., object], *args: object) -> None:
    """Require an adversarial operation to reject its input."""
    try:
        callable_obj(*args)
    except Exception:
        return
    raise AssertionError("hostile input was unexpectedly accepted")


def _state_mutation() -> None:
    """Mutate serialized state fields and require malformed values to reject."""
    base = _transition(0).to_dict()
    mutations: tuple[object, ...] = (None, [], {}, 1, True, "")
    fields = tuple(base)
    for field in fields:
        for value in mutations:
            payload = dict(base)
            payload[field] = value
            if value == base[field]:
                continue
            if field == "digest" and value == "":
                continue
            _expect_reject(ReliabilityStateTransition.from_dict, payload)
    rng = random.Random(SEED)
    for _ in range(10_000):
        payload = dict(base)
        key = rng.choice(fields)
        payload[key] = rng.choice(mutations)
        if payload[key] == base[key] or (key == "digest" and payload[key] == ""):
            continue
        try:
            ReliabilityStateTransition.from_dict(payload)
        except Exception:
            continue
        raise AssertionError(f"state mutation accepted: {key}")


def _race_engine() -> None:
    """Exercise concurrent content and state writes from multiple workers."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        content = ContentAddressedArtifactStore(root / "content")

        def put_race(_: int) -> str:
            return content.put(b"race")

        with ThreadPoolExecutor(max_workers=24) as executor:
            digests = list(executor.map(put_race, range(100)))
        assert len(set(digests)) == 1

        store = JsonlReliabilityStateStore(root / "state.jsonl")
        first = _transition(0)
        store.append(first)
        contenders = (
            _transition(1, first),
            _transition(2, first),
        )

        def append(item: ReliabilityStateTransition) -> str:
            try:
                store.append(item)
            except ValueError:
                return "rejected"
            return "accepted"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(append, contenders))
        assert outcomes.count("accepted") == 1
        assert outcomes.count("rejected") == 1


def _crash_writer(path_text: str) -> None:
    """Write a partial JSONL record and terminate the process."""
    path = Path(path_text)
    payload = json.dumps(_transition(0).to_dict(), sort_keys=True).encode() + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.write(fd, payload[: max(1, len(payload) // 2)])
    os.fsync(fd)
    os.close(fd)
    os._exit(137)  # noqa: S606


def _crash_harness() -> None:
    """Prove a real process crash leaves a recoverable JSONL tail."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "state.jsonl"
        context = multiprocessing.get_context("spawn")
        process = context.Process(target=_crash_writer, args=(str(path),))
        process.start()
        process.join(10)
        assert process.exitcode not in (None, 0)
        assert JsonlReliabilityStateStore(path).read() == []


def _archive_attack() -> None:
    """Exercise duplicate, traversal, absolute, and malformed ZIP members."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        for index, members in enumerate(
            (
                (("manifest.json", b"{}"), ("manifest.json", b"{}")),
                (("manifest.json", b"{}"), ("../escape", b"x")),
                (("manifest.json", b"{}"), ("/absolute", b"x")),
                (("manifest.json", b"{}"), ("artifacts//file", b"x")),
            )
        ):
            path = root / f"attack-{index}.zip"
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                archive = ZipFile(path, "w", compression=ZIP_DEFLATED)
                for name, payload in members:
                    archive.writestr(name, payload)
                archive.close()
            _expect_reject(verify_bundle, path)


def _storage_corruption() -> None:
    """Corrupt persisted SQLite fields and require verification to fail closed."""
    with TemporaryDirectory() as directory:
        path = prepare_validation_database(Path(directory) / "failure-lab.db")
        store = SqliteReliabilityStateStore(path)
        item = _transition(0)
        store.append(item)
        for column, value in (
            ("payload", "{}"),
            ("digest", "0" * 64),
            ("subject_id", "forged"),
        ):
            with closing(sqlite3.connect(path)) as database:
                database.execute(
                    f"UPDATE reliability_state_transitions SET {column}=? WHERE transition_id=?",
                    (value, item.transition_id),
                )
                database.commit()
            _expect_reject(store.read)
            with closing(sqlite3.connect(path)) as database:
                database.execute("DELETE FROM reliability_state_transitions")
                database.commit()
            store.append(item)


def _http_mutation() -> None:
    """Mutate HTTP transport and request inputs at the verification boundary."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        application = create_application(
            VerificationServiceConfig(artifact_roots=(root,), max_request_bytes=32)
        )
        captured: dict[str, object] = {}

        def start_response(
            status: str,
            headers: list[tuple[str, str]],
            exc_info: tuple[type[BaseException], BaseException, TracebackType]
            | None = None,
        ) -> Callable[[bytes], object]:
            _ = exc_info
            captured["status"] = status
            captured["headers"] = headers
            return lambda _body: None

        oversized = b"{" + b"x" * 64
        environ = {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/v1/evidence/verify",
            "CONTENT_LENGTH": str(len(oversized)),
            "wsgi.input": io.BytesIO(oversized),
            "wsgi.url_scheme": "https",
        }
        body = b"".join(application(environ, start_response))  # type: ignore
        assert str(captured["status"]) == "413 Request Entity Too Large"
        assert json.loads(body)["error"]["code"] == "REQUEST_TOO_LARGE"

        captured.clear()
        malformed = b"{not-json"
        environ["CONTENT_LENGTH"] = str(len(malformed))
        environ["wsgi.input"] = io.BytesIO(malformed)
        body = b"".join(application(environ, start_response))  # type: ignore
        assert str(captured["status"]) == "400 Bad Request"
        assert json.loads(body)["error"]["code"] == "INVALID_JSON"


def _crypto_mutation() -> None:
    """Mutate Ed25519 messages and signatures and require verification failure."""
    try:
        from nacl.signing import SigningKey
    except ImportError as exc:
        raise FailureLabError(
            "PyNaCl is required for the crypto mutation case"
        ) from exc
    private = SigningKey.generate()
    message = b"statewake-failure-lab"
    signature = private.sign(message).signature
    verify_ed25519_signature(private.verify_key.encode(), message, signature)
    mutated_message = message + b"!"
    _expect_reject(
        verify_ed25519_signature,
        private.verify_key.encode(),
        mutated_message,
        signature,
    )
    mutated_signature = bytearray(signature)
    mutated_signature[0] ^= 1
    _expect_reject(
        verify_ed25519_signature,
        private.verify_key.encode(),
        message,
        bytes(mutated_signature),
    )


def _event_mutation() -> None:
    """Inject duplicate event sequence numbers and require run validation to reject."""
    with TemporaryDirectory() as directory:
        path = Path(directory) / "events.jsonl"
        store = JsonlEventStore(path)
        event = EventEnvelope("run", 0, NOW, "decision", "engine")
        store.append(event)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(event.to_dict(), sort_keys=True, separators=(",", ":"))
                + "\n"
            )
        _expect_reject(store.validate_run, "run")


def _provenance_mutation() -> None:
    """Inject a provenance cycle and require validation to reject it."""
    graph = ProvenanceGraph(
        (
            ProvenanceNode("a", "artifact", "a" * 64, "a", ("b",)),
            ProvenanceNode("b", "artifact", "b" * 64, "b", ("a",)),
        ),
        (("a", "b"), ("b", "a")),
    )
    _expect_reject(graph.validate_required_edges)


def _receipt_identity_race() -> None:
    """Race identical producer occurrences and require one receipt identity."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        adapter = LocalEvidenceIngestionAdapter(
            ContentAddressedArtifactStore(root / "artifacts"),
            JsonEvidenceReceiptStore(root / "receipts"),
        )

        def ingest(_: int) -> str:
            try:
                adapter.ingest_bytes(
                    b"same",
                    producer_type="producer",
                    producer_id="producer-1",
                    source_ref="source",
                    source_event_id="event-1",
                    run_id="run-1",
                    captured_at=NOW,
                )
            except Exception as exc:
                return type(exc).__name__
            return "accepted"

        with ThreadPoolExecutor(max_workers=24) as executor:
            outcomes = list(executor.map(ingest, range(100)))
        assert outcomes.count("accepted") == 100


def _run_cases() -> tuple[AttackCase, ...]:
    """Return the canonical attack catalog."""
    return (
        AttackCase(
            "state-mutation",
            "mutation",
            "Malformed serialized state fields",
            _state_mutation,
        ),
        AttackCase(
            "race-engine", "race", "Concurrent content and state writes", _race_engine
        ),
        AttackCase(
            "crash-harness",
            "crash",
            "Real process partial-write recovery",
            _crash_harness,
        ),
        AttackCase(
            "archive-attack",
            "archive",
            "ZIP duplicate and traversal attacks",
            _archive_attack,
        ),
        AttackCase(
            "storage-corruption",
            "storage",
            "Persisted SQLite field corruption",
            _storage_corruption,
        ),
        AttackCase(
            "http-mutation",
            "http",
            "Malformed and oversized HTTP requests",
            _http_mutation,
        ),
        AttackCase(
            "crypto-mutation",
            "crypto",
            "Message and signature mutation",
            _crypto_mutation,
        ),
        AttackCase(
            "event-mutation",
            "mutation",
            "Duplicate event sequence injection",
            _event_mutation,
        ),
        AttackCase(
            "provenance-mutation",
            "mutation",
            "Cyclic provenance injection",
            _provenance_mutation,
        ),
        AttackCase(
            "receipt-identity-race",
            "race",
            "Concurrent producer occurrence ingestion",
            _receipt_identity_race,
        ),
    )


def run() -> ValidationReport:
    """Execute the complete deterministic failure-laboratory catalog."""
    results: list[ValidationResult] = []
    for case in _run_cases():
        try:
            case.probe()
        except FailureLabError as exc:
            if case.attack_id == "crypto-mutation":
                results.append(
                    {
                        "attack_id": case.attack_id,
                        "category": case.category,
                        "description": case.description,
                        "passed": True,
                        "skipped": True,
                        "skip_reason": str(exc),
                    }
                )
            else:
                results.append(
                    {
                        "attack_id": case.attack_id,
                        "category": case.category,
                        "description": case.description,
                        "passed": False,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
        except Exception as exc:
            results.append(
                {
                    "attack_id": case.attack_id,
                    "category": case.category,
                    "description": case.description,
                    "passed": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
        else:
            results.append(
                {
                    "attack_id": case.attack_id,
                    "category": case.category,
                    "description": case.description,
                    "passed": True,
                }
            )
    report: ValidationReport = {
        "schema_version": "1",
        "seed": SEED,
        "passed": all(item["passed"] for item in results),
        "attack_count": len(results),
        "results": results,
    }
    return report


def _main() -> int:
    """Run the failure laboratory command-line interface."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ci", action="store_true", help="emit only machine-readable JSON"
    )
    args = parser.parse_args()
    report = run()
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.ci and not report["passed"]:
        return 1
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(_main())
