"""Native SDK observation boundary, separate from legacy mapping adapters.

Completed executions become runtime contracts; checkpoint/state snapshots and
instrumentation events become point-in-time observation contracts. Raw SDK
payloads are not persisted; callers can inspect explicit capture failures.
"""

from __future__ import annotations

import json
import os
from _thread import LockType
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING

from statewake.ai_contracts.observation import ObservationContract
from statewake.ai_contracts.runtime import RuntimeTraceContract
from statewake.integrations.base import ContractCaptureResult, capture_contract

if TYPE_CHECKING:
    from statewake.workspace import StateWakeWorkspace


def utc_time(value: object | None) -> datetime:
    """Convert supported native timestamp shapes to timezone-aware UTC."""
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("native event timestamp must include timezone")
        return value.astimezone(UTC)
    if isinstance(value, int) and not isinstance(value, bool):
        # OpenTelemetry SDK timestamps are integer nanoseconds since epoch.
        return datetime.fromtimestamp(value / 1_000_000_000, UTC)
    if isinstance(value, str):
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError("native event timestamp must include timezone")
        return result.astimezone(UTC)
    raise ValueError("native event timestamp must be observed and valid")


def digest_observed(value: object) -> str:
    """Digest observed structured content without unstable object ``repr`` values.

    Strings and bytes retain their native bytes. JSON-compatible structured
    payloads are canonicalized. Opaque SDK objects are rejected instead of
    producing a misleading digest of a process-specific representation.
    """
    if isinstance(value, bytes):
        return sha256(value).hexdigest()
    if isinstance(value, str):
        return sha256(value.encode("utf-8")).hexdigest()
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
            ensure_ascii=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("observed content is not JSON-serializable") from exc
    return sha256(encoded).hexdigest()


def digest_sdk_observed(value: object) -> str:
    """Digest observed SDK models without relying on their text representations.

    Native LangChain responses and messages are SDK objects, not plain strings.
    Only a JSON-mode model export or an already JSON-compatible value is
    accepted. Unknown shapes fail explicitly rather than receiving a repr hash.
    """

    def to_json(value: object) -> object:
        """Convert supported SDK values to JSON-compatible data."""
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        if isinstance(value, (bytes, bytearray)):
            raise ValueError("binary SDK objects require an explicit byte boundary")
        if isinstance(value, (list, tuple)):
            return [to_json(item) for item in value]
        if isinstance(value, Mapping):
            if not all(isinstance(key, str) for key in value):
                raise ValueError("SDK payload has a non-string mapping key")
            return {key: to_json(item) for key, item in value.items()}
        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            return to_json(model_dump(mode="json"))
        raise ValueError("SDK object has no supported JSON serialization")

    return digest_observed(to_json(value))


def safe_metadata(**items: object) -> dict[str, str]:
    """Select known non-payload identifiers; never copy arbitrary SDK metadata."""
    allowed = {
        "event_kind",
        "operation",
        "checkpoint_id",
        "parent_checkpoint_id",
        "thread_id",
        "node",
        "model_name",
        "provider",
        "tool_name",
        "status",
        "snapshot_digest",
        "task_count",
        "interrupt_count",
        "parent_span_id",
        "timestamp_origin",
        "native_timestamp_status",
    }
    result: dict[str, str] = {}
    for key, value in items.items():
        # A custom SDK object may put a raw prompt/secret into __str__. Never
        # stringify arbitrary producer objects on the privacy boundary.
        if key not in allowed or not isinstance(value, (str, int, bool)):
            continue
        text = str(value).strip()
        if not text or len(text) > 128 or not text.isprintable():
            continue
        result[key] = text
    return result


class NativeCaptureCapacityError(ValueError):
    """The bounded native capture queue cannot admit another result."""


@dataclass(slots=True)
class NativeCaptureSink:
    """Bounded native capture with optional synchronous workspace/journal durability.

    Without ``workspace``, captured results are only an in-memory diagnostic
    window, not durable evidence. With a workspace, a result is persisted before
    being acknowledged. Failure journals contain only stage and exception type;
    never raw exceptions or SDK content. Journal replay is intentionally bounded.
    """

    results: list[ContractCaptureResult] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    capacity: int = 1024
    failure_capacity: int = 1024
    failure_journal_max_bytes: int = 8 * 1024 * 1024
    workspace: StateWakeWorkspace | None = None
    failure_journal: Path | None = None
    failure_count: int = field(default=0, init=False)
    _lock: LockType = field(default_factory=Lock, repr=False)

    def __post_init__(self) -> None:
        """Validate bounds and replay a configured failure journal."""
        if (
            self.capacity <= 0
            or self.failure_capacity <= 0
            or self.failure_journal_max_bytes <= 0
        ):
            raise ValueError("capture capacities must be positive")
        if (
            len(self.results) > self.capacity
            or len(self.failures) > self.failure_capacity
        ):
            raise ValueError("initial capture buffers exceed capacity")
        if self.workspace is not None and self.failure_journal is None:
            raise ValueError("durable capture requires a failure journal")
        if self.failure_journal is not None:
            self.failure_journal = Path(self.failure_journal)
            if self.failure_journal.is_symlink() or any(
                part.is_symlink() for part in self.failure_journal.parents
            ):
                raise ValueError("failure journal path cannot traverse a symlink")
            if (
                self.failure_journal.exists()
                and self.failure_journal.stat().st_size > self.failure_journal_max_bytes
            ):
                raise NativeCaptureCapacityError(
                    "failure journal exceeds its size limit"
                )
            if self.failure_journal.exists():
                with self.failure_journal.open("r", encoding="utf-8") as journal:
                    for line in journal:
                        item = json.loads(line)
                        if (
                            not isinstance(item, dict)
                            or set(item) != {"stage", "error_type"}
                            or not all(
                                isinstance(item.get(key), str)
                                and 0 < len(item[key]) <= 128
                                and all(
                                    char.isascii() and (char.isalnum() or char in "._-")
                                    for char in item[key]
                                )
                                for key in ("stage", "error_type")
                            )
                        ):
                            raise ValueError("invalid failure journal entry")
                        self.failure_count += 1
                        self.failures.append(f"{item['stage']}: {item['error_type']}")
                        if len(self.failures) > self.failure_capacity:
                            self.failures.pop(0)

    def add(self, result: ContractCaptureResult) -> None:
        """Persist if configured; reject overflow without losing evidence silently."""
        with self._lock:
            if len(self.results) >= self.capacity:
                self._record_failure(
                    "native_capture.capacity", "NativeCaptureCapacityError"
                )
                raise NativeCaptureCapacityError(
                    "native capture result capacity exceeded"
                )
            if self.workspace is not None:
                try:
                    result.persist(self.workspace)
                except Exception as exc:
                    self._record_failure("native_capture.persist", type(exc).__name__)
                    raise
            self.results.append(result)

    def _record_failure(self, stage: str, error_type: str) -> None:
        """Record a privacy-safe failure under the sink lock."""
        if (
            not error_type
            or len(error_type) > 128
            or not all(
                char.isascii() and (char.isalnum() or char in "._-")
                for char in error_type
            )
        ):
            error_type = "UnclassifiedError"
        record = {"stage": stage, "error_type": error_type}
        if self.failure_journal is not None:
            self.failure_journal.parent.mkdir(parents=True, exist_ok=True)
            if self.failure_journal.is_symlink() or any(
                part.is_symlink() for part in self.failure_journal.parents
            ):
                raise ValueError("failure journal path cannot traverse a symlink")
            line = json.dumps(record, separators=(",", ":")) + "\n"
            size = (
                self.failure_journal.stat().st_size
                if self.failure_journal.exists()
                else 0
            )
            if size + len(line.encode("utf-8")) > self.failure_journal_max_bytes:
                raise NativeCaptureCapacityError(
                    "failure journal exceeds its size limit"
                )
            with self.failure_journal.open("a", encoding="utf-8") as journal:
                journal.write(line)
                journal.flush()
                os.fsync(journal.fileno())
        self.failure_count += 1
        self.failures.append(f"{stage}: {error_type}")
        if len(self.failures) > self.failure_capacity:
            self.failures.pop(0)

    def fail(self, stage: str, exc: Exception) -> None:
        """Journal a failure without persisting the exception message."""
        # Caller-controlled stages must not inject log records or unbounded text.
        if (
            not stage
            or len(stage) > 128
            or not all(c.isascii() and (c.isalnum() or c in "._-") for c in stage)
        ):
            stage = "native_capture.invalid_stage"
        with self._lock:
            self._record_failure(stage, type(exc).__name__)

    def snapshot(self) -> tuple[ContractCaptureResult, ...]:
        """Return the bounded, stable in-memory result window."""
        with self._lock:
            return tuple(self.results)

    def drain(self) -> tuple[ContractCaptureResult, ...]:
        """Acknowledge and clear the in-memory window after downstream handling."""
        with self._lock:
            items = tuple(self.results)
            self.results.clear()
            return items


def capture_native_runtime(
    sink: NativeCaptureSink,
    *,
    framework: str,
    run_id: str,
    trace_id: str,
    span_id: str,
    started_at: object,
    ended_at: object | None,
    parent_run_id: str | None = None,
    error_status: str | None = None,
    metadata: Mapping[str, str] | None = None,
) -> ContractCaptureResult:
    """Create and store a genuine native runtime observation contract."""
    if started_at is None or ended_at is None:
        raise ValueError("completed runtime observation requires start and end times")
    started = utc_time(started_at)
    ended = utc_time(ended_at)
    result = capture_contract(
        RuntimeTraceContract(
            contract_version=f"{framework}.native.runtime.v1",
            producer_id=f"{framework}-native",
            run_id=run_id,
            framework=framework,
            trace_id=trace_id,
            span_id=span_id,
            started_at=started,
            ended_at=ended,
            captured_at=ended,
            parent_run_id=parent_run_id,
            error_status=error_status,
            metadata=dict(metadata or {}),
        )
    )
    sink.add(result)
    return result


def capture_native_observation(
    sink: NativeCaptureSink,
    *,
    framework: str,
    run_id: str,
    trace_id: str,
    span_id: str,
    observed_at: object,
    observation_kind: str,
    parent_run_id: str | None = None,
    metadata: Mapping[str, str] | None = None,
) -> ContractCaptureResult:
    """Record point-in-time state/event evidence without inventing duration."""
    if observed_at is None:
        raise ValueError("native observation requires an observed timestamp")
    result = capture_contract(
        ObservationContract(
            contract_version=f"{framework}.native.observation.v1",
            producer_id=f"{framework}-native",
            run_id=run_id,
            framework=framework,
            trace_id=trace_id,
            span_id=span_id,
            observation_kind=observation_kind,
            observed_at=utc_time(observed_at),
            parent_run_id=parent_run_id,
            metadata=dict(metadata or {}),
        )
    )
    sink.add(result)
    return result
