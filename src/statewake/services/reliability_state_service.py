"""Application service for authoritative, evidence-backed reliability state transitions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from ..adapters.reliability_state import (
    JsonlReliabilityStateStore,
    ReliabilityStateStore,
)
from ..domain.operational_hooks import (
    NullReliabilityFailureHook,
    ReliabilityFailureEvent,
    ReliabilityFailureHook,
)
from ..domain.reliability_evidence import ReliabilityEvidenceChain
from ..domain.reliability_state import (
    ALLOWED_TRANSITIONS,
    ReliabilityStateSnapshot,
    ReliabilityStateTransition,
)
from ..services.reliability_evidence_service import (
    load_reliability_evidence_chain,
    verify_reliability_evidence_chain,
)


def _transition_id(
    subject_id: str,
    previous_digest: str,
    chain: ReliabilityEvidenceChain,
    occurred_at: datetime,
) -> str:
    """Return the deterministic transition identifier for the requested state change."""
    payload = {
        "subject_id": subject_id,
        "previous_transition_digest": previous_digest,
        "evidence_chain_id": chain.chain_id,
        "evidence_chain_digest": chain.digest(),
        "occurred_at": occurred_at.astimezone(UTC).isoformat(),
        "decision": chain.decision,
        "to_state": chain.reliability_state,
    }
    return sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def current_reliability_state(
    subject_id: str,
    *,
    store: ReliabilityStateStore,
) -> ReliabilityStateSnapshot:
    """Return the authoritative current reliability state for a subject."""
    transitions = store.read(subject_id)
    if not transitions:
        return ReliabilityStateSnapshot(
            subject_id=subject_id,
            state="unknown",
            transition_id=None,
            transition_digest=None,
            evidence_chain_id=None,
        )
    latest = transitions[-1]
    return ReliabilityStateSnapshot(
        subject_id=subject_id,
        state=latest.to_state,
        transition_id=latest.transition_id,
        transition_digest=latest.computed_digest,
        evidence_chain_id=latest.evidence_chain_id,
    )


def transition_reliability_state(
    subject_id: str,
    chain: ReliabilityEvidenceChain,
    *,
    store: ReliabilityStateStore,
    actor: str,
    occurred_at: datetime | None = None,
    rationale: tuple[str, ...] = (),
    evidence_root: Path | None = None,
    failure_hook: ReliabilityFailureHook | None = None,
) -> ReliabilityStateTransition:
    """Persist and return a validated reliability-state transition."""
    if not subject_id.strip():
        raise ValueError("subject_id must not be empty.")
    when = occurred_at or datetime.now(UTC)
    if when.tzinfo is None:
        raise ValueError("occurred_at must be timezone-aware.")
    hook = failure_hook or NullReliabilityFailureHook()
    if evidence_root is not None:
        try:
            verify_reliability_evidence_chain(chain, root=evidence_root)
        except Exception as exc:
            hook.emit(
                ReliabilityFailureEvent.now(
                    "verification_failure",
                    "verify_evidence_chain",
                    str(exc),
                    subject_id=subject_id,
                )
            )
            raise
    current = current_reliability_state(subject_id, store=store)
    target = chain.reliability_state
    if (
        current.state == target
        and current.transition_id is not None
        and current.evidence_chain_id == chain.chain_id
    ):
        history = store.read(subject_id)
        return history[-1]
    if target not in ALLOWED_TRANSITIONS[current.state]:
        raise ValueError(
            f"invalid reliability-state transition: {current.state} -> {target}"
        )
    if chain.decision == "accept" and target not in {"reliable", "recovered"}:
        raise ValueError("accept decision must produce reliable or recovered state.")
    if chain.decision == "review" and target != "degraded":
        raise ValueError("review decision must produce degraded state.")
    if chain.decision == "reject" and target != "unreliable":
        raise ValueError("reject decision must produce unreliable state.")
    if target == "recovered":
        if current.state != "unreliable":
            raise ValueError("recovered state requires an unreliable predecessor.")
        if chain.recovery_ref is None or chain.reconciliation_state != "recovered":
            raise ValueError(
                "recovered state requires a recovery reference and recovered reconciliation state."
            )
    transition_id = _transition_id(
        subject_id, current.transition_digest or "", chain, when
    )
    transition = ReliabilityStateTransition(
        transition_id=transition_id,
        subject_id=subject_id,
        from_state=current.state,
        to_state=target,
        occurred_at=when,
        actor=actor,
        evidence_chain_id=chain.chain_id,
        evidence_chain_digest=chain.digest(),
        decision=chain.decision,
        rationale=rationale or chain.decision_rationale,
        previous_transition_digest=current.transition_digest or "",
    )
    try:
        return store.append(transition)
    except Exception as exc:
        hook.emit(
            ReliabilityFailureEvent.now(
                "state_write_failure",
                "append_reliability_state",
                str(exc),
                subject_id=subject_id,
            )
        )
        raise


def transition_reliability_state_from_file(
    subject_id: str,
    chain_path: Path,
    *,
    history_path: Path,
    actor: str,
    evidence_root: Path | None = None,
    occurred_at: datetime | None = None,
    rationale: tuple[str, ...] = (),
) -> ReliabilityStateTransition:
    """Load, validate, and persist a reliability-state transition from a file."""
    chain = load_reliability_evidence_chain(chain_path)
    return transition_reliability_state(
        subject_id,
        chain,
        store=JsonlReliabilityStateStore(history_path),
        actor=actor,
        evidence_root=evidence_root,
        occurred_at=occurred_at,
        rationale=rationale,
    )


def reliability_state_history(
    subject_id: str,
    *,
    history_path: Path,
) -> list[dict[str, Any]]:
    """Return the validated reliability-state history for a subject."""
    return [
        item.to_dict()
        for item in JsonlReliabilityStateStore(history_path).read(subject_id)
    ]
