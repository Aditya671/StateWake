"""Composition service for the V1 verifiable reliability-evidence chain."""

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

from statewake.domain.evidence_receipt import ExternalEvidenceReceipt
from statewake.services.persistence import atomic_write_text

from ..domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)


def _file_digest(path: Path) -> str:
    """Return the SHA-256 digest of a file."""
    return sha256(path.read_bytes()).hexdigest()


def _artifact_identity(path: Path, *fields: str) -> str:
    """Prefer an artifact's canonical identity over its storage filename."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return path.name
    if isinstance(payload, Mapping):
        for field in fields:
            value = str(payload.get(field, ""))
            if value.strip():
                return value
    return path.name


def _ref(
    kind: str,
    identity: str,
    path: Path | None = None,
    digest: str | None = None,
    *,
    receipt_ref: EvidenceReference | None = None,
) -> EvidenceReference:
    """Create a canonical evidence reference for an artifact."""
    if digest is None:
        if path is None:
            raise ValueError(f"{kind} requires a path or digest.")
        digest = _file_digest(path)
    return EvidenceReference(
        kind=kind,
        identity=identity,
        digest=digest,
        source=None if path is None else path.name,
        receipt_ref=receipt_ref,
    )


def build_reliability_evidence_chain(
    *,
    run_id: str,
    run_path: Path,
    state_id: str,
    state_path: Path,
    evidence_paths: tuple[Path, ...],
    provenance_path: Path,
    integrity_proof_path: Path,
    verification_status: str = "verified",
    reliability_state: str = "reliable",
    reconciliation_state: str = "verified",
    reconciliation_path: Path | None = None,
    recovery_path: Path | None = None,
    attestation_path: Path | None = None,
    decision_basis_path: Path | None = None,
    decision_basis_kind: str = "decision-basis",
    decision: str = "accept",
    rationale: tuple[str, ...] = (),
    evidence_receipt_paths: Mapping[str, Path] | None = None,
    comparison_path: Path | None = None,
    reconciliation_binding_path: Path | None = None,
) -> ReliabilityEvidenceChain:
    """Build the canonical reliability evidence chain from artifact references."""
    if verification_status == "verified" and not evidence_paths:
        raise ValueError("verified chain requires evidence references.")
    receipt_paths = evidence_receipt_paths or {}
    sorted_evidence = tuple(sorted(evidence_paths, key=lambda p: str(p)))
    evidence_refs: list[EvidenceReference] = []
    evidence_chain_identity: list[dict[str, str | None]] = []
    for path in sorted_evidence:
        receipt_path = receipt_paths.get(str(path)) or receipt_paths.get(path.name)
        receipt_ref = None
        if receipt_path is not None:
            receipt = ExternalEvidenceReceipt.from_dict(
                json.loads(receipt_path.read_text(encoding="utf-8"))
            )
            if receipt.artifact_digest != _file_digest(path):
                raise ValueError(
                    f"evidence receipt artifact digest does not match evidence source: {path}"
                )
            if receipt.artifact_size != path.stat().st_size:
                raise ValueError(
                    f"evidence receipt artifact size does not match evidence source: {path}"
                )
            receipt_ref = receipt.receipt_reference(source=receipt_path.name)
            if receipt.provenance_ref is not None and (
                receipt.provenance_ref.identity != provenance_path.name
                or receipt.provenance_ref.digest != _file_digest(provenance_path)
            ):
                raise ValueError(
                    f"evidence receipt provenance does not match reliability provenance: {path}"
                )
            if receipt.run_id is not None and receipt.run_id != run_id:
                raise ValueError(
                    f"evidence receipt run_id does not match reliability run: {path}"
                )
        evidence_identity = path.name if receipt_ref is None else receipt_ref.identity
        evidence_ref = _ref(
            "evidence", evidence_identity, path, receipt_ref=receipt_ref
        )
        evidence_refs.append(evidence_ref)
        evidence_chain_identity.append(
            {
                "path": str(path),
                "digest": evidence_ref.digest,
                "receipt_id": None if receipt_ref is None else receipt_ref.identity,
                "receipt_digest": None if receipt_ref is None else receipt_ref.digest,
            }
        )
    chain_payload = {
        "run_id": run_id,
        "run_digest": _file_digest(run_path),
        "state_id": state_id,
        "state_digest": _file_digest(state_path),
        "evidence": evidence_chain_identity,
        "provenance_digest": _file_digest(provenance_path),
        "integrity_digest": _file_digest(integrity_proof_path),
    }
    comparison_ref = None
    if comparison_path is not None:
        from .reliability_comparison_service import (
            load_reliability_behavioral_comparison,
        )

        comparison = load_reliability_behavioral_comparison(comparison_path)
        comparison_ref = _ref("comparison", comparison.comparison_id, comparison_path)
        chain_payload["comparison"] = {  # type: ignore
            "identity": comparison_ref.identity,
            "digest": comparison_ref.digest,
        }
    reconciliation_binding_ref = None
    if reconciliation_binding_path is not None:
        if comparison_path is None or reconciliation_path is None:
            raise ValueError(
                "reconciliation_binding_path requires both comparison_path and reconciliation_path"
            )
        from .reliability_reconciliation_binding_service import (
            load_reliability_reconciliation_binding,
            verify_reliability_reconciliation_binding,
        )

        binding = load_reliability_reconciliation_binding(reconciliation_binding_path)
        reconciliation_ref = _ref(
            "reconciliation",
            _artifact_identity(reconciliation_path, "reconciliation_id", "bundle_id"),
            reconciliation_path,
        )
        comparison_ref = _ref("comparison", comparison.comparison_id, comparison_path)  # type: ignore
        verify_reliability_reconciliation_binding(
            binding,
            comparison=comparison,  # type: ignore
            reconciliation_path=reconciliation_path,
            root=reconciliation_binding_path.parent,
        )
        if (
            binding.comparison_id != comparison_ref.identity
            or binding.comparison_digest != comparison_ref.digest
        ):
            raise ValueError(
                "reconciliation binding does not match comparison reference"
            )
        if (
            binding.reconciliation_id != reconciliation_ref.identity
            or binding.reconciliation_digest != reconciliation_ref.digest
        ):
            raise ValueError(
                "reconciliation binding does not match reconciliation reference"
            )
        reconciliation_binding_ref = _ref(
            "reconciliation-binding", binding.digest, reconciliation_binding_path
        )
        chain_payload["reconciliation_binding"] = {  # type: ignore
            "identity": reconciliation_binding_ref.identity,
            "digest": reconciliation_binding_ref.digest,
        }

    decision_basis_ref = None
    if decision_basis_path is not None:
        from .reliability_decision_basis_service import load_reliability_decision_basis

        basis = load_reliability_decision_basis(decision_basis_path)
        expected_kind = "policy" if basis.basis_type == "policy" else "decision-basis"
        if decision_basis_kind != expected_kind:
            raise ValueError(
                "decision_basis_kind does not match the decision-basis artifact type"
            )
        if basis.decision != decision or basis.reliability_state != reliability_state:
            raise ValueError(
                "decision-basis decision/state does not match requested reliability decision"
            )
        if tuple(basis.rationale) != tuple(rationale):
            raise ValueError(
                "decision-basis rationale does not match requested reliability rationale"
            )
        decision_basis_ref = _ref(
            decision_basis_kind, basis.basis_id, decision_basis_path
        )
        chain_payload["decision_basis"] = {  # type: ignore
            "kind": decision_basis_kind,
            "identity": decision_basis_ref.identity,
            "digest": decision_basis_ref.digest,
        }
    chain_id = sha256(
        json.dumps(chain_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return ReliabilityEvidenceChain(
        chain_id=chain_id,
        run=_ref("run", run_id, run_path),
        state=_ref("state", state_id, state_path),
        evidence=tuple(evidence_refs),
        provenance=_ref("provenance", provenance_path.name, provenance_path),
        integrity=_ref("integrity", integrity_proof_path.name, integrity_proof_path),
        verification_status=verification_status,
        reliability_state=reliability_state,
        reconciliation_state=reconciliation_state,
        reconciliation_ref=None
        if reconciliation_path is None
        else _ref(
            "reconciliation",
            _artifact_identity(reconciliation_path, "reconciliation_id", "bundle_id"),
            reconciliation_path,
        ),
        recovery_ref=None
        if recovery_path is None
        else _ref(
            "recovery", _artifact_identity(recovery_path, "recovery_id"), recovery_path
        ),
        attestation_ref=None
        if attestation_path is None
        else _ref("attestation", attestation_path.name, attestation_path),
        decision_basis_ref=decision_basis_ref,
        comparison_ref=comparison_ref,
        reconciliation_binding_ref=reconciliation_binding_ref,
        decision=decision,
        decision_rationale=rationale,
    )


def _safe_source(root: Path, source: str) -> Path:
    """Return a sanitized source identifier suitable for persisted diagnostics."""
    candidate = (root / source.replace("\\", "/")).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"reliability evidence source escapes root: {source}")
    return candidate


def verify_external_evidence_receipts(
    chain: ReliabilityEvidenceChain, *, root: Path
) -> None:
    """Verify receipt bindings from evidence back to canonical producer occurrences."""
    root = root.resolve()
    for index, evidence_ref in enumerate(chain.evidence):
        receipt_ref = evidence_ref.receipt_ref
        if receipt_ref is None:
            continue
        if receipt_ref.kind != "receipt" or receipt_ref.source is None:
            raise ValueError(
                f"evidence reference {evidence_ref.identity} has an incomplete receipt binding"
            )
        receipt_path = _safe_source(root, receipt_ref.source)
        if not receipt_path.is_file():
            raise FileNotFoundError(
                f"evidence receipt source not found: {receipt_path}"
            )
        receipt = ExternalEvidenceReceipt.from_dict(
            json.loads(receipt_path.read_text(encoding="utf-8"))
        )
        if receipt.receipt_id != receipt_ref.identity:
            raise ValueError(
                f"evidence receipt identity mismatch for evidence {index}: expected {receipt_ref.identity}, got {receipt.receipt_id}"
            )
        if receipt.digest != receipt_ref.digest:
            raise ValueError(
                f"evidence receipt digest mismatch for {receipt.receipt_id}: expected {receipt_ref.digest}, got {receipt.digest}"
            )
        if evidence_ref.identity != receipt.receipt_id:
            raise ValueError(
                f"evidence reference identity is not bound to receipt {receipt.receipt_id}"
            )
        if evidence_ref.digest != receipt.artifact_digest:
            raise ValueError(
                f"evidence artifact digest is not bound to receipt {receipt.receipt_id}"
            )
        if evidence_ref.source is None:
            raise ValueError(
                f"receipt-bound evidence {evidence_ref.identity} must retain a verifiable local artifact source"
            )
        evidence_path = _safe_source(root, evidence_ref.source)
        if not evidence_path.is_file():
            raise FileNotFoundError(
                f"receipt-bound evidence artifact not found: {evidence_path}"
            )
        content = evidence_path.read_bytes()
        if len(content) != receipt.artifact_size:
            raise ValueError(
                f"receipt artifact size mismatch for {receipt.receipt_id}: expected {receipt.artifact_size}, got {len(content)}"
            )
        if sha256(content).hexdigest() != receipt.artifact_digest:
            raise ValueError(
                f"receipt artifact digest mismatch for {receipt.receipt_id}"
            )
        if receipt.run_id is not None and receipt.run_id != chain.run.identity:
            raise ValueError(
                f"evidence receipt run_id is not bound to reliability run {chain.run.identity}"
            )
        if receipt.provenance_ref is not None:
            if receipt.provenance_ref.kind != "provenance":
                raise ValueError(
                    f"evidence receipt {receipt.receipt_id} has an invalid provenance reference"
                )
            if (
                receipt.provenance_ref.identity != chain.provenance.identity
                or receipt.provenance_ref.digest != chain.provenance.digest
            ):
                raise ValueError(
                    f"evidence receipt provenance is not bound to reliability provenance for"
                    f"{receipt.receipt_id}"
                )


def verify_reliability_evidence_chain(
    chain: ReliabilityEvidenceChain, *, root: Path
) -> None:
    """Verify every locally referenced source and its canonical external-evidence bindings."""
    root = root.resolve()
    refs = (
        chain.run,
        chain.state,
        *chain.evidence,
        chain.provenance,
        chain.integrity,
        chain.reconciliation_ref,
        chain.recovery_ref,
        chain.attestation_ref,
        chain.comparison_ref,
    )
    for reference in refs:
        if reference is None or reference.source is None:
            continue
        candidate = _safe_source(root, reference.source)
        if not candidate.is_file():
            raise FileNotFoundError(
                f"reliability evidence source not found: {candidate}"
            )
        actual = _file_digest(candidate)
        if actual != reference.digest:
            raise ValueError(
                f"reliability evidence source digest mismatch for {reference.identity}: expected {reference.digest}, got {actual}"
            )
    verify_external_evidence_receipts(chain, root=root)
    if chain.comparison_ref is not None:
        from .reliability_comparison_service import (
            load_reliability_behavioral_comparison,
            verify_reliability_behavioral_comparison,
        )

        comparison_path = _safe_source(root, chain.comparison_ref.source or "")
        comparison = load_reliability_behavioral_comparison(comparison_path)
        if comparison.comparison_id != chain.comparison_ref.identity:
            raise ValueError(
                "comparison identity does not match reliability evidence chain"
            )
        if _file_digest(comparison_path) != chain.comparison_ref.digest:
            raise ValueError(
                "comparison artifact digest does not match reliability evidence chain"
            )
        verify_reliability_behavioral_comparison(comparison, root=root)
    if chain.reconciliation_binding_ref is not None:
        if chain.comparison_ref is None or chain.reconciliation_ref is None:
            raise ValueError(
                "reconciliation binding requires both comparison and reconciliation references"
            )
        from .reliability_reconciliation_binding_service import (
            load_reliability_reconciliation_binding,
            verify_reliability_reconciliation_binding,
        )

        binding_path = _safe_source(root, chain.reconciliation_binding_ref.source or "")
        binding = load_reliability_reconciliation_binding(binding_path)
        if binding.digest != chain.reconciliation_binding_ref.identity:
            raise ValueError("reconciliation binding identity mismatch")
        if _file_digest(binding_path) != chain.reconciliation_binding_ref.digest:
            raise ValueError("reconciliation binding artifact digest mismatch")
        comparison_path = _safe_source(root, chain.comparison_ref.source or "")
        comparison = __import__(
            "statewake.services.reliability_comparison_service",
            fromlist=["load_reliability_behavioral_comparison"],
        ).load_reliability_behavioral_comparison(comparison_path)
        reconciliation_path = _safe_source(root, chain.reconciliation_ref.source or "")
        verify_reliability_reconciliation_binding(
            binding,
            comparison=comparison,
            reconciliation_path=reconciliation_path,
            root=root,
        )
        if (
            binding.comparison_id != chain.comparison_ref.identity
            or binding.comparison_digest != chain.comparison_ref.digest
        ):
            raise ValueError("reconciliation binding comparison mismatch")
        if (
            binding.reconciliation_id != chain.reconciliation_ref.identity
            or binding.reconciliation_digest != chain.reconciliation_ref.digest
        ):
            raise ValueError("reconciliation binding reconciliation mismatch")
    from .reliability_decision_basis_service import verify_reliability_decision_basis

    verify_reliability_decision_basis(chain, root=root)


def write_reliability_evidence_chain(
    chain: ReliabilityEvidenceChain, path: Path
) -> None:
    """Persist a reliability evidence chain."""
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        path, json.dumps(chain.to_dict(), indent=2, sort_keys=True) + "\n"
    )


def load_reliability_evidence_chain(path: Path) -> ReliabilityEvidenceChain:
    """Load and validate a persisted reliability evidence chain."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("reliability evidence chain root must be an object.")
    return ReliabilityEvidenceChain.from_dict(payload)
