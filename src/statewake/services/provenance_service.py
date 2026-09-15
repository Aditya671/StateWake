"""Cross-artifact provenance loading, digest verification, and integrity proofs."""

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

from statewake.utils.json_support import load_object

from ..domain.operations import OperationalBundle
from ..domain.provenance import (
    IntegrityProof,
    ProvenanceGraph,
    ProvenanceNode,
)
from ..services.persistence import atomic_write_text


def _canonical_bytes(payload: Any) -> bytes:  # type: ignore
    """Return canonical bytes for deterministic provenance hashing."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def load_provenance_graph(path: Path) -> ProvenanceGraph:
    """Load and validate a persisted provenance graph."""
    payload = load_object(path)
    if not isinstance(payload, dict):
        raise ValueError("provenance graph root must be an object.")
    raw_nodes = payload.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise ValueError("nodes must be a non-empty JSON array.")
    nodes = []
    for raw in raw_nodes:
        if not isinstance(raw, dict):
            raise ValueError("each provenance node must be an object.")
        nodes.append(
            ProvenanceNode(
                node_id=str(raw.get("node_id", "")),
                kind=str(raw.get("kind", "")),
                digest=str(raw.get("digest", "")),
                identity=str(raw.get("identity", "")),
                derived_from=tuple(str(value) for value in raw.get("derived_from", [])),  # type: ignore
                path=None if raw.get("path") is None else str(raw["path"]),
            )
        )
    raw_edges = payload.get("required_edges", [])
    if not isinstance(raw_edges, list):
        raise ValueError("required_edges must be a JSON array.")
    edges = []
    for edge in raw_edges:
        if not isinstance(edge, list) or len(edge) != 2:
            raise ValueError("each required edge must be a two-item array.")
        edges.append((str(edge[0]), str(edge[1])))
    graph = ProvenanceGraph(tuple(nodes), tuple(edges))
    supplied = payload.get("graph_digest")
    if supplied is not None and supplied != graph.graph_digest():
        raise ValueError("provenance graph digest does not match contents.")
    return graph


def build_provenance_graph_for_bundle(
    bundle_path: Path, bundle: OperationalBundle
) -> ProvenanceGraph:
    """Build a deterministic provenance graph for an operational bundle."""
    nodes = [
        ProvenanceNode(
            node_id=item.artifact_id,
            kind=item.kind,
            digest=item.sha256,
            identity=f"artifact:{item.artifact_id}",
            derived_from=item.derived_from,
        )
        for item in bundle.artifacts
    ]
    nodes.append(
        ProvenanceNode(
            node_id="bundle",
            kind="operational_bundle",
            digest=sha256(bundle_path.read_bytes()).hexdigest(),
            identity=f"bundle:{bundle.bundle_id}",
            derived_from=tuple(item.artifact_id for item in bundle.artifacts),
        )
    )
    required_edges = tuple(
        (child.node_id, parent) for child in nodes for parent in child.derived_from
    )
    required_edges += tuple(("bundle", item.artifact_id) for item in bundle.artifacts)
    return ProvenanceGraph(tuple(nodes), required_edges)


def verify_bundle_provenance(
    bundle_path: Path, bundle: OperationalBundle
) -> tuple[ProvenanceGraph, IntegrityProof]:
    """Verify provenance identity and reachability for an operational bundle."""
    graph = build_provenance_graph_for_bundle(bundle_path, bundle)
    expected_reachability = tuple(
        ("bundle", item.artifact_id) for item in bundle.artifacts
    )
    proof = build_integrity_proof(graph, reachable_pairs=expected_reachability)
    if not proof.verified:
        raise ValueError("operational bundle provenance integrity verification failed.")

    bundle_node = graph.node("bundle")
    actual_bundle_digest = sha256(bundle_path.read_bytes()).hexdigest()
    if (
        bundle_node.digest != actual_bundle_digest
        or bundle_node.identity != f"bundle:{bundle.bundle_id}"
    ):
        raise ValueError("operational bundle provenance identity or digest mismatch.")

    expected_artifacts = {item.artifact_id: item for item in bundle.artifacts}
    for node in graph.nodes:
        if node.node_id == "bundle":
            continue
        artifact = expected_artifacts.get(node.node_id)
        if (
            artifact is None
            or node.kind != artifact.kind
            or node.digest != artifact.sha256
        ):
            raise ValueError(
                f"operational bundle provenance artifact mismatch: {node.node_id}"
            )
        if node.identity != f"artifact:{artifact.artifact_id}":
            raise ValueError(
                f"operational bundle provenance artifact identity mismatch: {node.node_id}"
            )
    return graph, proof


def verify_artifact_digests(graph: ProvenanceGraph, *, root: Path) -> None:
    """Verify that all provenance artifact digests match their sources."""
    mismatches = []
    for node in graph.nodes:
        if node.path is None:
            continue
        candidate = (root / node.path).resolve()
        if root.resolve() not in candidate.parents and candidate != root.resolve():
            raise ValueError(
                f"provenance artifact path escapes graph directory: {node.path}"
            )
        if not candidate.is_file():
            raise FileNotFoundError(f"provenance artifact not found: {candidate}")
        actual = sha256(candidate.read_bytes()).hexdigest()
        if actual != node.digest:
            mismatches.append(f"{node.node_id}: expected {node.digest}, got {actual}")
    if mismatches:
        raise ValueError(
            "provenance artifact digest mismatches: " + "; ".join(mismatches)
        )


def build_integrity_proof(
    graph: ProvenanceGraph,
    *,
    identities: Mapping[str, str] | None = None,
    reachable_pairs: tuple[tuple[str, str], ...] = (),
) -> IntegrityProof:
    """Build a deterministic integrity proof for the provenance graph."""
    required_edges_ok = False
    identity_ok = False
    try:
        graph.validate_required_edges()
        required_edges_ok = True
    except ValueError:
        required_edges_ok = False
    if identities is None:
        identity_ok = True
    else:
        try:
            graph.verify_identities(identities)
            identity_ok = True
        except ValueError:
            identity_ok = False
    pair_results_list = []
    for child, parent in reachable_pairs:
        try:
            result = graph.reachable(child, parent)
        except KeyError:
            result = False
        pair_results_list.append((child, parent, result))
    pair_results = tuple(pair_results_list)
    reachable_ok = all(result for _, _, result in pair_results)
    return IntegrityProof(
        graph_digest=graph.graph_digest(),
        required_edges_verified=required_edges_ok,
        required_identities_verified=identity_ok,
        reachable_pairs=pair_results,
        verified=required_edges_ok and identity_ok and reachable_ok,
    )


def verify_provenance_graph(
    path: Path,
    *,
    identities: Mapping[str, str] | None = None,
    reachable_pairs: tuple[tuple[str, str], ...] = (),
    verify_files: bool = True,
) -> IntegrityProof:
    """Verify provenance structure, identities, and bound artifact digests."""
    graph = load_provenance_graph(path)
    if verify_files:
        verify_artifact_digests(graph, root=path.parent)
    return build_integrity_proof(
        graph, identities=identities, reachable_pairs=reachable_pairs
    )


def write_provenance_proof(path: Path, proof: IntegrityProof) -> None:
    """Persist a provenance integrity proof."""
    atomic_write_text(
        path, json.dumps(proof.to_dict(), indent=2, sort_keys=True) + "\n"
    )
