"""Build and verify the V1 discrepancy-to-reconciliation binding."""

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

from statewake.utils.json_support import load_object

from ..domain.reliability_comparison import ReliabilityBehavioralComparison
from ..domain.reliability_reconciliation_binding import ReliabilityReconciliationBinding
from ..services.persistence import atomic_write_text


def _file_digest(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    return sha256(path.read_bytes()).hexdigest()


def _safe(root: Path, source: str) -> Path:  # type: ignore
    """Return a sanitized value suitable for reconciliation diagnostics."""
    candidate = (root.resolve() / source.replace("\\", "/")).resolve()
    if candidate != root.resolve() and root.resolve() not in candidate.parents:
        raise ValueError(f"reconciliation source escapes root: {source}")
    return candidate


def _reconciliation_semantics(path: Path) -> tuple[str, str]:
    """Return the canonical reconciliation semantics bound to this artifact."""
    payload = load_object(path)
    if not isinstance(payload, Mapping):  # type: ignore
        raise ValueError("reconciliation artifact must be a JSON object")
    identity = str(payload.get("reconciliation_id", payload.get("bundle_id", "")))
    status = str(payload.get("status", payload.get("state", "")))
    if not identity.strip():
        raise ValueError("reconciliation artifact lacks a canonical identity")
    if status not in {"verified", "recovered"}:
        raise ValueError("reconciliation result must be verified or recovered")
    return identity, status


def build_reliability_reconciliation_binding(
    *,
    comparison_path: Path,
    reconciliation_path: Path,
    output: Path,
) -> ReliabilityReconciliationBinding:
    """Build a deterministic binding between comparison and reconciliation artifacts."""
    comparison = ReliabilityBehavioralComparison.from_dict(load_object(comparison_path))
    reconciliation_id, reconciliation_status = _reconciliation_semantics(
        reconciliation_path
    )
    resolved = comparison.discrepancy
    if not resolved:
        raise ValueError(
            "a reconciliation binding requires at least one detected discrepancy"
        )
    binding = ReliabilityReconciliationBinding(
        format_version="1",
        comparison_id=comparison.comparison_id,
        comparison_digest=_file_digest(comparison_path),
        reconciliation_id=reconciliation_id,
        reconciliation_digest=_file_digest(reconciliation_path),
        reconciliation_status=reconciliation_status,
        resolved_discrepancies=resolved,
    )
    atomic_write_text(
        output, json.dumps(binding.to_dict(), indent=2, sort_keys=True) + "\n"
    )
    return binding


def verify_reliability_reconciliation_binding(
    binding: ReliabilityReconciliationBinding,
    *,
    comparison: ReliabilityBehavioralComparison,
    reconciliation_path: Path,
    root: Path,
) -> None:
    """Require an exact comparison/discrepancy and exact successful reconciliation result."""
    resolved_root = root.resolve()
    reconciliation_path = reconciliation_path.resolve()
    if (
        reconciliation_path != resolved_root
        and resolved_root not in reconciliation_path.parents
    ):
        raise ValueError("reconciliation path escapes root")
    if not reconciliation_path.is_file():
        raise FileNotFoundError(reconciliation_path)
    if binding.comparison_id != comparison.comparison_id:
        raise ValueError("reconciliation binding comparison identity mismatch")
    if binding.resolved_discrepancies != comparison.discrepancy:
        raise ValueError("reconciliation binding discrepancy set mismatch")
    actual = _file_digest(reconciliation_path)
    if actual != binding.reconciliation_digest:
        raise ValueError("reconciliation binding reconciliation digest mismatch")
    identity, status = _reconciliation_semantics(reconciliation_path)
    if identity != binding.reconciliation_id:
        raise ValueError("reconciliation binding reconciliation identity mismatch")
    if status != binding.reconciliation_status:
        raise ValueError("reconciliation binding reconciliation status mismatch")


def load_reliability_reconciliation_binding(
    path: Path,
) -> ReliabilityReconciliationBinding:
    """Load and validate a persisted reconciliation binding."""  # ruff: ignore[missing-blank-line-after-summary]
    payload = load_object(path)
    if not isinstance(payload, Mapping):  # type: ignore
        raise ValueError("reconciliation binding root must be an object")
    return ReliabilityReconciliationBinding.from_dict(payload)
