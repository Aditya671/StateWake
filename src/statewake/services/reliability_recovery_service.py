"""Verification helpers for the V1 durable recovery outcome boundary."""

from __future__ import annotations

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
import json
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import Any

from statewake.utils.json_support import load_object, require_bool
from statewake.utils.time import parse_datetime

from ..domain.reliability_evidence import ReliabilityEvidenceChain
from ..domain.reliability_recovery_outcome import ReliabilityRecoveryOutcome


def _file_digest(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    return sha256(path.read_bytes()).hexdigest()


def _safe_source(root: Path, source: str) -> Path:
    """Return a sanitized source identifier suitable for persisted diagnostics."""
    resolved_root = root.resolve()
    candidate = (resolved_root / source.replace("\\", "/")).resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ValueError(f"reliability recovery source escapes root: {source}")
    return candidate


def _recovery_payload(path: Path) -> Mapping[str, Any]:
    """Build the canonical recovery payload for verification and persistence."""
    payload = load_object(path)
    if not isinstance(payload, dict):
        raise ValueError("recovery artifact must be a JSON object.")
    return payload


def _reconciliation_payload(path: Path) -> Mapping[str, Any]:
    """Build the canonical reconciliation payload for verification and persistence."""
    payload = load_object(path)
    if not isinstance(payload, dict):
        raise ValueError("reconciliation artifact must be a JSON object.")
    return payload


def _verify_recovery_record(payload: Mapping[str, Any]) -> None:
    """Validate the legacy recovery record shape without importing its legacy module."""
    required = {
        "recovery_id",
        "occurred_at",
        "impact_id",
        "source_reconciliation_id",
        "actor",
        "approved",
        "status",
        "steps",
        "reason",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(
            "recovery artifact is missing required fields: " + ", ".join(missing)
        )
    occurred_at = parse_datetime(str(payload["occurred_at"]), field="occurred_at")
    if occurred_at.tzinfo is None:
        raise ValueError("recovery artifact occurred_at must be timezone-aware")
    for field in ("recovery_id", "impact_id", "source_reconciliation_id", "actor"):
        if not str(payload[field]).strip():
            raise ValueError(f"recovery artifact {field} must not be empty")
    status = str(payload["status"])
    if status not in {"planned", "applied", "partially-applied", "failed"}:
        raise ValueError("unsupported remediation recovery status")
    approved = require_bool(payload.get("approved", False), field="approved")
    if status == "applied" and not approved:
        raise ValueError("applied remediation recovery must be approved")
    steps = payload["steps"]
    if not isinstance(steps, list):
        raise ValueError("recovery artifact steps must be a list")
    step_fields = {"step_id", "target", "action", "status", "reason"}
    valid_step_statuses = {"pending", "applied", "failed", "skipped"}
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("recovery artifact step must be a JSON object")
        missing_step = sorted(step_fields - set(step))
        if missing_step:
            raise ValueError(
                "recovery artifact step is missing required fields: "
                + ", ".join(missing_step)
            )
        if not str(step["target"]).strip() or not str(step["action"]).strip():
            raise ValueError("recovery artifact step target/action must not be empty")
        if str(step["status"]) not in valid_step_statuses:
            raise ValueError("unsupported remediation step status")
    unsigned = dict(payload)
    supplied_digest = str(unsigned.pop("digest", ""))
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    expected_digest = sha256(canonical).hexdigest()
    if supplied_digest and supplied_digest != expected_digest:
        raise ValueError("remediation recovery digest mismatch")


def verify_reliability_recovery_outcome(
    chain: ReliabilityEvidenceChain,
    *,
    root: Path,
) -> ReliabilityRecoveryOutcome:
    """Verify that a recovered reliability state is backed by exact recovery semantics."""
    if chain.reliability_state != "recovered":
        raise ValueError(
            "recovery outcome verification applies only to recovered reliability state"
        )
    if chain.recovery_ref is None:
        raise ValueError("recovered reliability outcome lacks a recovery reference")
    if chain.reconciliation_ref is None:
        raise ValueError(
            "recovered reliability outcome lacks a reconciliation reference"
        )
    if chain.recovery_ref.kind != "recovery":
        raise ValueError("recovery reference must have kind 'recovery'")
    if chain.reconciliation_ref.kind != "reconciliation":
        raise ValueError("reconciliation reference must have kind 'reconciliation'")
    if chain.recovery_ref.source is None or chain.reconciliation_ref.source is None:
        raise ValueError(
            "recovery and reconciliation references must retain verifiable local sources"
        )

    resolved_root = root.resolve()
    recovery_path = _safe_source(resolved_root, chain.recovery_ref.source)
    reconciliation_path = _safe_source(resolved_root, chain.reconciliation_ref.source)
    if not recovery_path.is_file():
        raise FileNotFoundError(f"recovery source not found: {recovery_path}")
    if not reconciliation_path.is_file():
        raise FileNotFoundError(
            f"reconciliation source not found: {reconciliation_path}"
        )

    recovery_digest = _file_digest(recovery_path)
    if recovery_digest != chain.recovery_ref.digest:
        raise ValueError(
            f"recovery artifact digest mismatch for {chain.recovery_ref.identity}: expected {chain.recovery_ref.digest}, got {recovery_digest}"
        )
    reconciliation_digest = _file_digest(reconciliation_path)
    if reconciliation_digest != chain.reconciliation_ref.digest:
        raise ValueError(
            f"reconciliation artifact digest mismatch for {chain.reconciliation_ref.identity}: expected {chain.reconciliation_ref.digest}, got {reconciliation_digest}"
        )

    recovery = _recovery_payload(recovery_path)
    reconciliation = _reconciliation_payload(reconciliation_path)

    recovery_id = str(recovery.get("recovery_id", ""))
    legacy_filename_identity = (
        Path(chain.recovery_ref.source).name if chain.recovery_ref.source else ""
    )
    if (
        recovery_id != chain.recovery_ref.identity
        and chain.recovery_ref.identity != legacy_filename_identity
    ):
        raise ValueError(
            "recovery artifact identity does not match its evidence reference"
        )
    # The serialized recovery file digest and the recovery record's own deterministic
    # semantic digest are distinct integrity domains; validate both independently.
    _verify_recovery_record(recovery)
    if str(recovery.get("status", "")) != "applied":
        raise ValueError("recovery artifact does not record an applied recovery result")

    reconciliation_id = str(
        reconciliation.get("bundle_id", reconciliation.get("reconciliation_id", ""))
    )
    if reconciliation_id != chain.reconciliation_ref.identity:
        raise ValueError(
            "reconciliation artifact identity does not match its evidence reference"
        )
    reconciliation_status = str(
        reconciliation.get("state", reconciliation.get("status", ""))
    )
    if reconciliation_status not in {"verified", "recovered"}:
        raise ValueError(
            "reconciliation artifact does not record a successful post-recovery result"
        )

    source_reconciliation_id = str(recovery.get("source_reconciliation_id", ""))
    if source_reconciliation_id != reconciliation_id:
        raise ValueError(
            "recovery artifact is not bound to the exact reconciliation result"
        )
    if chain.reconciliation_state != "recovered":
        raise ValueError(
            "recovered reliability outcome requires recovered reconciliation state"
        )

    return ReliabilityRecoveryOutcome(
        format_version="1",
        recovery_id=chain.recovery_ref.identity,
        recovery_digest=chain.recovery_ref.digest,
        recovery_status=str(recovery["status"]),
        source_reconciliation_id=source_reconciliation_id,
        reconciliation_id=reconciliation_id,
        reconciliation_digest=chain.reconciliation_ref.digest,
        reconciliation_status=reconciliation_status,
    )
