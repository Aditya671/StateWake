"""Cross-artifact lineage closure for the V1 reliability-proof boundary."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from statewake.domain.provenance import ProvenanceGraph
from statewake.utils.json_support import load_object

from ..domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from ..domain.reliability_lineage import (
    ReliabilityLineageBinding,
    ReliabilityLineageClosure,
)
from .provenance_service import load_provenance_graph, verify_artifact_digests


def _material_references(
    chain: ReliabilityEvidenceChain, *, root: Path | None = None
) -> tuple[tuple[str, EvidenceReference], ...]:
    """Return the material artifact references required for lineage verification."""
    items: list[tuple[str, EvidenceReference]] = [
        ("run", chain.run),
        ("state", chain.state),
    ]
    for index, reference in enumerate(chain.evidence):
        items.append((f"evidence:{index}", reference))
    if chain.decision_basis_ref is not None:
        items.append(("decision_basis", chain.decision_basis_ref))
    if chain.comparison_ref is not None:
        items.append(("comparison", chain.comparison_ref))
        if root is not None and chain.comparison_ref.source is not None:
            from .reliability_comparison_service import (
                comparison_input_references,
                load_reliability_behavioral_comparison,
            )

            comparison_path = (
                root.resolve() / chain.comparison_ref.source.replace("\\", "/")
            ).resolve()
            if comparison_path.is_file():
                comparison = load_reliability_behavioral_comparison(comparison_path)
                for item in comparison_input_references(comparison):
                    items.append(
                        (f"comparison-input:{item.kind}:{item.identity}", item)
                    )
    if chain.reconciliation_ref is not None:
        items.append(("reconciliation", chain.reconciliation_ref))
    if chain.recovery_ref is not None:
        items.append(("recovery", chain.recovery_ref))
    return tuple(items)


def _binding_for_reference(
    graph: ProvenanceGraph, role: str, reference: EvidenceReference
) -> ReliabilityLineageBinding:
    """Return the lineage binding associated with an evidence reference."""
    matches = [
        node
        for node in graph.nodes
        if node.identity == reference.identity and node.digest == reference.digest
    ]
    if len(matches) == 0:
        raise ValueError(
            f"provenance lineage node not found for {role}: {reference.identity}"
        )
    if len(matches) != 1:
        raise ValueError(
            f"provenance lineage identity is ambiguous for {role}: {reference.identity}"
        )
    node = matches[0]
    return ReliabilityLineageBinding(
        role=role, node_id=node.node_id, identity=node.identity, digest=node.digest
    )


def build_reliability_lineage_closure(
    chain: ReliabilityEvidenceChain, *, root: Path
) -> ReliabilityLineageClosure:
    """Build a deterministic semantic closure over the existing provenance graph."""
    root = root.resolve()
    if chain.provenance.source is None:
        raise ValueError(
            "reliability provenance reference must retain a local graph source"
        )
    graph_path = (root / chain.provenance.source.replace("\\", "/")).resolve()
    if graph_path != root and root not in graph_path.parents:
        raise ValueError(
            f"reliability provenance source escapes evidence root: {chain.provenance.source}"
        )
    if not graph_path.is_file():
        raise FileNotFoundError(
            f"reliability provenance source not found: {graph_path}"
        )
    if sha256(graph_path.read_bytes()).hexdigest() != chain.provenance.digest:
        raise ValueError(
            "reliability provenance graph file digest does not match the evidence chain"
        )
    graph = load_provenance_graph(graph_path)
    verify_artifact_digests(graph, root=root)
    graph.validate_required_edges()

    bindings = tuple(
        _binding_for_reference(graph, role, reference)
        for role, reference in _material_references(chain, root=root)
    )
    run_node = next(item for item in bindings if item.role == "run")
    reachable_roles = tuple(item.role for item in bindings if item.role != "run")
    for item in bindings:
        if item.role == "run":
            continue
        if not graph.reachable(item.node_id, run_node.node_id):
            raise ValueError(
                f"provenance lineage is not connected to declared run for {item.role}: {item.identity}"
            )

    if chain.decision_basis_ref is not None:
        basis_path = (
            (root / chain.decision_basis_ref.source.replace("\\", "/")).resolve()
            if chain.decision_basis_ref.source
            else None
        )
        if basis_path is None or not basis_path.is_file():
            raise FileNotFoundError(
                "decision basis source is required for lineage closure"
            )
        basis = load_object(basis_path)
        input_digests = tuple(str(item) for item in basis.get("input_digests", []))  # type: ignore
        chain_input_digests = {
            chain.run.digest,
            chain.state.digest,
            *(item.digest for item in chain.evidence),
        }
        if chain.reconciliation_ref is not None:
            chain_input_digests.add(chain.reconciliation_ref.digest)
        if chain.recovery_ref is not None:
            chain_input_digests.add(chain.recovery_ref.digest)
        missing = [item for item in input_digests if item not in chain_input_digests]
        if missing:
            raise ValueError(
                f"decision-basis input is outside the reliability chain lineage: {missing}"
            )
        for digest in input_digests:
            role_candidates = [item for item in bindings if item.digest == digest]
            if not role_candidates:
                raise ValueError(
                    f"decision-basis input lacks a provenance lineage node: {digest}"
                )
            basis_node = next(
                item for item in bindings if item.role == "decision_basis"
            )
            if not any(
                graph.reachable(basis_node.node_id, candidate.node_id)
                for candidate in role_candidates
            ):
                raise ValueError(
                    f"decision-basis lineage does not reach declared input: {digest}"
                )

    return ReliabilityLineageClosure(
        format_version="1",
        provenance_graph_digest=graph.graph_digest(),
        run_role="run",
        bindings=bindings,
        reachable_roles=reachable_roles,
    )


def verify_reliability_lineage_closure(
    chain: ReliabilityEvidenceChain,
    *,
    root: Path,
    closure: ReliabilityLineageClosure | None = None,
) -> ReliabilityLineageClosure:
    """Verify the semantic lineage witness against the existing provenance authority."""
    built = build_reliability_lineage_closure(chain, root=root)
    if closure is not None and closure != built:
        raise ValueError(
            "packaged reliability lineage closure does not match the provenance graph"
        )
    return built
