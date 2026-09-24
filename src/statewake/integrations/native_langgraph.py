"""Native LangGraph checkpoint history capture without replacing graph storage."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from statewake.ai_contracts.base import canonical_json_bytes, sha256_hex
from statewake.integrations.native_capture import (
    NativeCaptureSink,
    capture_native_observation,
    safe_metadata,
)


def _snapshot_config(value: object) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    return {}


def capture_langgraph_history(
    graph: Any,
    config: Mapping[str, Any],
    sink: NativeCaptureSink,
    *,
    limit: int | None = None,
) -> tuple[Any, ...]:
    """Read real ``get_state_history`` snapshots; retain state digest only.

    A configured checkpointer and thread_id are required. Missing checkpoint
    identity is a capture failure, never a fabricated version or run success.
    """
    if "thread_id" not in _snapshot_config(config.get("configurable")):
        raise ValueError("LangGraph history requires configurable.thread_id")
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    snapshots = graph.get_state_history(dict(config), limit=limit)
    recorded: list[Any] = []
    for snapshot in snapshots:
        try:
            values = snapshot.values
            # Reject opaque/unserializable state rather than hashing repr.
            digest = sha256_hex(canonical_json_bytes({"values": values}))
            cfg = _snapshot_config(snapshot.config)
            configurable = _snapshot_config(cfg.get("configurable"))
            checkpoint_id = configurable.get("checkpoint_id")
            if not checkpoint_id:
                raise ValueError("snapshot missing checkpoint identity")
            parent_cfg = _snapshot_config(getattr(snapshot, "parent_config", None))
            parent = _snapshot_config(parent_cfg.get("configurable")).get(
                "checkpoint_id"
            )
            run_id = str(
                configurable.get("thread_id") or config["configurable"]["thread_id"]
            )
            result = capture_native_observation(
                sink,
                framework="langgraph",
                run_id=run_id,
                trace_id=run_id,
                span_id=str(checkpoint_id),
                observed_at=getattr(snapshot, "created_at", None),
                observation_kind="checkpoint",
                parent_run_id=str(parent) if parent else None,
                metadata=safe_metadata(
                    event_kind="checkpoint",
                    thread_id=run_id,
                    checkpoint_id=checkpoint_id,
                    parent_checkpoint_id=parent,
                    snapshot_digest=digest,
                    task_count=len(getattr(snapshot, "tasks", ())),
                    interrupt_count=len(getattr(snapshot, "interrupts", ())),
                ),
            )
            recorded.append(result)
        except (ValueError, TypeError, AttributeError) as exc:
            sink.fail("langgraph.snapshot", exc)
    return tuple(recorded)
