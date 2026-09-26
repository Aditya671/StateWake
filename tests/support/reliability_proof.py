"""Shared fixtures for reliability-proof regression tests."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from statewake.adapters.reliability_attestation import (
    JsonlReliabilityOutcomeAttestationStore,
)
from statewake.adapters.reliability_state import JsonlReliabilityStateStore
from statewake.domain.provenance import ProvenanceGraph, ProvenanceNode
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.services.reliability_attestation_service import (
    attest_reliability_outcome,
    write_reliability_outcome_attestation,
)
from statewake.services.reliability_evidence_service import (
    write_reliability_evidence_chain,
)
from statewake.services.reliability_state_service import transition_reliability_state

NOW = datetime(2026, 9, 11, 0, 0, tzinfo=UTC)


def _refresh_lineage_graph(
    root: Path, chain: ReliabilityEvidenceChain
) -> ReliabilityEvidenceChain:
    """Refresh the provenance lineage graph for the test fixture."""
    refs: list[tuple[str, EvidenceReference]] = [
        ("run", chain.run),
        ("state", chain.state),
    ]
    for index, item in enumerate(chain.evidence):
        refs.append((f"evidence:{index}", item))
    if chain.decision_basis_ref is not None:
        refs.append(("decision_basis", chain.decision_basis_ref))
    if chain.reconciliation_ref is not None:
        refs.append(("reconciliation", chain.reconciliation_ref))
    if chain.recovery_ref is not None:
        refs.append(("recovery", chain.recovery_ref))
    nodes: list[ProvenanceNode] = []
    role_node: dict[str, str] = {}
    for role, ref in refs:
        node_id = role.replace(":", "-")
        role_node[role] = node_id
        parents: tuple[str, ...] = () if role == "run" else ("run",)
        nodes.append(
            ProvenanceNode(
                node_id=node_id,
                kind=ref.kind,
                digest=ref.digest,
                identity=ref.identity,
                derived_from=parents,
            )
        )
    # A decision basis derives from each exact declared input available in the chain.
    if chain.decision_basis_ref is not None:
        source = chain.decision_basis_ref.source
        if source is None:
            raise AssertionError("decision basis reference must have a source path")
        basis_path = root / source
        payload: dict[str, object] = json.loads(basis_path.read_text(encoding="utf-8"))
        input_digests = tuple(str(x) for x in payload.get("input_digests", []))  # type: ignore
        digest_nodes: dict[str, str] = {n.digest: n.node_id for n in nodes}
        input_parents: tuple[str, ...] = tuple(
            digest_nodes[x] for x in input_digests if x in digest_nodes
        ) or ("run",)
        basis_id = role_node["decision_basis"]
        nodes = [
            n
            if n.node_id != basis_id
            else ProvenanceNode(n.node_id, n.kind, n.digest, n.identity, input_parents)
            for n in nodes
        ]
    graph = ProvenanceGraph(
        tuple(nodes),
        tuple((node.node_id, parent) for node in nodes for parent in node.derived_from),
    )
    provenance_source = chain.provenance.source or "provenance.json"
    provenance_path = root / provenance_source
    provenance_path.write_text(
        json.dumps(graph.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return replace(
        chain,
        provenance=EvidenceReference(
            "provenance",
            chain.provenance.identity,
            sha256(provenance_path.read_bytes()).hexdigest(),
            provenance_path.name,
        ),
    )


def prepare_reliability_proof_fixture(root: Path) -> tuple[Path, Path, Path]:
    """Prepare the shared reliability-proof fixture used by related tests."""
    for name, payload in (
        ("run.json", {"run": "r1"}),
        ("state.json", {"state": "reliable"}),
        ("evidence.json", {"evidence": "e1"}),
        ("provenance.json", {"provenance": "p1"}),
        ("integrity.json", {"integrity": "verified"}),
    ):
        (root / name).write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    def ref(kind: str, identity: str, filename: str) -> EvidenceReference:
        """Build an evidence reference for a fixture file."""
        path = root / filename
        return EvidenceReference(
            kind, identity, sha256(path.read_bytes()).hexdigest(), filename
        )

    chain = ReliabilityEvidenceChain(
        chain_id="chain-1",
        run=ref("run", "run-1", "run.json"),
        state=ref("state", "state-1", "state.json"),
        evidence=(ref("evidence", "e1", "evidence.json"),),
        provenance=ref("provenance", "p1", "provenance.json"),
        integrity=ref("integrity", "i1", "integrity.json"),
        verification_status="verified",
        reliability_state="reliable",
        reconciliation_state="verified",
        decision="accept",
        decision_rationale=("all inputs verified",),
    )
    chain = _refresh_lineage_graph(root, chain)
    chain_path = root / "chain.json"
    write_reliability_evidence_chain(chain, chain_path)
    history_path = root / "history.jsonl"
    transition = transition_reliability_state(
        "agent-1",
        chain,
        store=JsonlReliabilityStateStore(history_path),
        actor="engine",
        occurred_at=NOW,
        evidence_root=root,
    )
    attestation = attest_reliability_outcome(
        chain,
        transition,
        actor="engine",
        store=JsonlReliabilityOutcomeAttestationStore(root / "attestations.jsonl"),
        occurred_at=NOW,
        signing_key_id="rel-key",
    )
    attestation_path = root / "attestation.json"
    write_reliability_outcome_attestation(attestation, attestation_path)
    return attestation_path, chain_path, history_path
