"""Read-only reliability decision-basis, reconciliation, and lineage investigation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256

from statewake.domain.reliability_comparison import ReliabilityBehavioralComparison
from statewake.domain.reliability_decision_basis import ReliabilityDecisionBasis
from statewake.domain.reliability_evidence import ReliabilityEvidenceChain
from statewake.domain.reliability_lineage import ReliabilityLineageClosure
from statewake.domain.reliability_reconciliation_binding import (
    ReliabilityReconciliationBinding,
)
from statewake.domain.reliability_recovery_outcome import ReliabilityRecoveryOutcome

DECISION_LINEAGE_SCHEMA_VERSION = "decision-lineage-investigation.v1"


def _digest(payload: dict[str, object]) -> str:
    """Return a deterministic digest for one JSON-compatible projection."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class DecisionLineageProjection:
    """Bounded operator view of one verified reliability decision chain."""

    payload: dict[str, object]

    @property
    def digest(self) -> str:
        """Return the deterministic ETag digest for this projection."""
        return _digest(self.payload)

    def to_dict(self) -> dict[str, object]:
        """Serialize the projection without source paths or raw artifact content."""
        return dict(self.payload)


def _reference_roles(chain: ReliabilityEvidenceChain) -> dict[str, list[str]]:
    """Map each chain digest to the semantic roles that reference it."""
    roles: dict[str, list[str]] = {}

    def add(digest: str, role: str) -> None:
        """Associate one semantic role with its referenced digest."""
        roles.setdefault(digest, []).append(role)

    add(chain.run.digest, "run")
    add(chain.state.digest, "state")
    for index, item in enumerate(chain.evidence):
        add(item.digest, f"evidence:{index}")
    add(chain.provenance.digest, "provenance")
    add(chain.integrity.digest, "integrity")
    optional = (
        ("reconciliation", chain.reconciliation_ref),
        ("recovery", chain.recovery_ref),
        ("attestation", chain.attestation_ref),
        ("comparison", chain.comparison_ref),
        ("reconciliation_binding", chain.reconciliation_binding_ref),
    )
    for role, reference in optional:
        if reference is not None:
            add(reference.digest, role)
    return roles


def _decision_inputs(
    chain: ReliabilityEvidenceChain,
    basis: ReliabilityDecisionBasis | None,
    lineage: ReliabilityLineageClosure,
) -> list[dict[str, object]]:
    """Project exact decision inputs with lineage/context classification."""
    if basis is None:
        return []
    roles_by_digest = _reference_roles(chain)
    graph_roles_by_digest: dict[str, list[str]] = {}
    for item in lineage.bindings:
        graph_roles_by_digest.setdefault(item.digest, []).append(item.role)
    reachable_roles = set(lineage.reachable_roles)

    result: list[dict[str, object]] = []
    for digest in basis.input_digests:
        graph_roles = sorted(graph_roles_by_digest.get(digest, []))
        semantic_roles = sorted(roles_by_digest.get(digest, []))
        lineage_bound = bool(graph_roles)
        result.append(
            {
                "digest": digest,
                "semantic_roles": semantic_roles,
                "classification": (
                    "lineage-bound" if lineage_bound else "verification-context"
                ),
                "lineage_roles": graph_roles,
                "reachable_to_run": (
                    all(
                        role == "run" or role in reachable_roles for role in graph_roles
                    )
                    if lineage_bound
                    else None
                ),
            }
        )
    return result


def _comparison_payload(
    comparison: ReliabilityBehavioralComparison | None,
) -> dict[str, object]:
    """Project one verified comparison without exposing local source paths or raw diff values."""
    if comparison is None:
        return {"present": False}
    return {
        "present": True,
        "comparison_id": comparison.comparison_id,
        "digest": comparison.digest,
        "significance": comparison.significance,
        "discrepancies": list(comparison.discrepancy),
        "before_inputs": [
            {
                "role": item.role,
                "kind": item.kind,
                "identity": item.identity,
                "digest": item.digest,
            }
            for item in comparison.before
        ],
        "after_inputs": [
            {
                "role": item.role,
                "kind": item.kind,
                "identity": item.identity,
                "digest": item.digest,
            }
            for item in comparison.after
        ],
    }


def _reconciliation_payload(
    binding: ReliabilityReconciliationBinding | None,
) -> dict[str, object]:
    """Project one verified discrepancy-to-reconciliation binding."""
    if binding is None:
        return {"present": False}
    return {
        "present": True,
        "binding_digest": binding.digest,
        "comparison_id": binding.comparison_id,
        "comparison_digest": binding.comparison_digest,
        "reconciliation_id": binding.reconciliation_id,
        "reconciliation_digest": binding.reconciliation_digest,
        "reconciliation_status": binding.reconciliation_status,
        "resolved_discrepancies": list(binding.resolved_discrepancies),
        "resolution": binding.resolution,
    }


def _recovery_payload(
    recovery: ReliabilityRecoveryOutcome | None,
) -> dict[str, object]:
    """Project a verified recovery outcome without inferring remediation success beyond it."""
    if recovery is None:
        return {"present": False}
    return {
        "present": True,
        "digest": recovery.digest,
        "recovery_id": recovery.recovery_id,
        "recovery_digest": recovery.recovery_digest,
        "recovery_status": recovery.recovery_status,
        "source_reconciliation_id": recovery.source_reconciliation_id,
        "reconciliation_id": recovery.reconciliation_id,
        "reconciliation_digest": recovery.reconciliation_digest,
        "reconciliation_status": recovery.reconciliation_status,
        "outcome": recovery.outcome,
    }


def build_decision_lineage_investigation(
    chain: ReliabilityEvidenceChain,
    lineage: ReliabilityLineageClosure,
    *,
    basis: ReliabilityDecisionBasis | None = None,
    comparison: ReliabilityBehavioralComparison | None = None,
    reconciliation_binding: ReliabilityReconciliationBinding | None = None,
    recovery: ReliabilityRecoveryOutcome | None = None,
) -> DecisionLineageProjection:
    """Project a fully verified decision/reconciliation/lineage chain for operators."""
    if chain.decision_basis_ref is not None and basis is None:
        raise ValueError("bound decision basis was not supplied to investigation")
    if basis is not None:
        if basis.basis_id != chain.decision_basis_ref.identity:  # type: ignore[union-attr]
            raise ValueError("decision basis identity does not match evidence chain")
        if basis.decision != chain.decision:
            raise ValueError("decision basis decision does not match evidence chain")
        if basis.reliability_state != chain.reliability_state:
            raise ValueError("decision basis state does not match evidence chain")
    if chain.comparison_ref is not None and comparison is None:
        raise ValueError("bound comparison was not supplied to investigation")
    if chain.reconciliation_binding_ref is not None and reconciliation_binding is None:
        raise ValueError(
            "bound reconciliation binding was not supplied to investigation"
        )
    if chain.reliability_state == "recovered" and recovery is None:
        raise ValueError("recovered chain requires verified recovery outcome")

    decision_basis_payload: dict[str, object]
    if basis is None:
        decision_basis_payload = {"present": False}
    else:
        decision_basis_payload = {
            "present": True,
            "basis_type": basis.basis_type,
            "basis_id": basis.basis_id,
            "version": basis.version,
            "digest": basis.digest,
            "decision": basis.decision,
            "reliability_state": basis.reliability_state,
            "input_count": len(basis.input_digests),
            "policy_id": basis.policy_id,
            "policy_version": basis.policy_version,
            "policy_digest": basis.policy_digest,
            "rationale_count": len(basis.rationale),
            "rationale_exposed": False,
        }

    payload: dict[str, object] = {
        "schema_version": DECISION_LINEAGE_SCHEMA_VERSION,
        "chain": {
            "chain_id": chain.chain_id,
            "digest": chain.digest(),
            "verification_status": chain.verification_status,
            "reliability_state": chain.reliability_state,
            "reconciliation_state": chain.reconciliation_state,
            "decision": chain.decision,
            "evidence_count": len(chain.evidence),
            "rationale_count": len(chain.decision_rationale),
            "rationale_exposed": False,
        },
        "decision_basis": decision_basis_payload,
        "decision_inputs": _decision_inputs(chain, basis, lineage),
        "comparison": _comparison_payload(comparison),
        "reconciliation": _reconciliation_payload(reconciliation_binding),
        "recovery": _recovery_payload(recovery),
        "lineage": {
            "verified": True,
            "provenance_graph_digest": lineage.provenance_graph_digest,
            "closure_digest": lineage.digest,
            "run_role": lineage.run_role,
            "reachable_roles": list(lineage.reachable_roles),
            "bindings": [
                {
                    "role": item.role,
                    "node_id": item.node_id,
                    "identity": item.identity,
                    "digest": item.digest,
                    "reachable_to_run": (
                        item.role == lineage.run_role
                        or item.role in lineage.reachable_roles
                    ),
                }
                for item in lineage.bindings
            ],
        },
        "verification": {
            "evidence_chain_verified": True,
            "decision_basis_verified": basis is not None,
            "comparison_verified": comparison is not None,
            "reconciliation_binding_verified": reconciliation_binding is not None,
            "recovery_outcome_verified": recovery is not None,
            "lineage_closure_verified": True,
        },
        "authorization": {
            "business_authorization_evaluated": False,
            "human_approval_evaluated": False,
            "publication_authorized": False,
        },
        "limitations": [
            (
                "Decision-basis and lineage verification establish exact recorded "
                "bindings; they do not prove factual correctness of an external system."
            ),
            (
                "Provenance and integrity digests may be valid decision inputs while "
                "remaining verification context rather than provenance-graph nodes."
            ),
            (
                "Reconciliation records that a declared discrepancy was bound to an "
                "accepted reconciliation result; it does not erase the discrepancy."
            ),
            (
                "Local source paths, raw artifacts, and free-form decision rationale "
                "are intentionally omitted from this read-only projection."
            ),
        ],
    }
    return DecisionLineageProjection(payload)


__all__ = [
    "DECISION_LINEAGE_SCHEMA_VERSION",
    "DecisionLineageProjection",
    "build_decision_lineage_investigation",
]
