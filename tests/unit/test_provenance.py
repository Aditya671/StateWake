"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from hashlib import sha256
from pathlib import Path
from typing import Any

from statewake.domain.provenance import ProvenanceGraph, ProvenanceNode
from statewake.services.provenance_service import (
    build_integrity_proof,
    verify_provenance_graph,
)


class TestProvenance(unittest.TestCase):
    """Provide regression coverage for the TestProvenance behavior."""

    def test_graph_requires_referenced_nodes_and_is_acyclic(self) -> None:
        """Verify the `test_graph_requires_referenced_nodes_and_is_acyclic` behavior
        and its expected invariants."""
        node_a = ProvenanceNode("policy", "policy", "a" * 64, "policy:base")
        node_b = ProvenanceNode(
            "effective", "effective_policy", "b" * 64, "effective:1", ("policy",)
        )
        graph = ProvenanceGraph((node_a, node_b), (("effective", "policy"),))
        proof = build_integrity_proof(graph, reachable_pairs=(("effective", "policy"),))
        self.assertTrue(proof.verified)
        self.assertEqual(graph.roots(), ("effective",))
        self.assertEqual(graph.graph_digest(), graph.graph_digest())

    def test_cycle_is_rejected(self) -> None:
        """Verify the `test_cycle_is_rejected` behavior and its expected invariants."""
        a = ProvenanceNode("a", "a", "a" * 64, "a", ("b",))
        b = ProvenanceNode("b", "b", "b" * 64, "b", ("a",))
        graph = ProvenanceGraph((a, b))
        with self.assertRaisesRegex(ValueError, "cycle"):
            graph.validate_acyclic()

    def test_identity_and_reachability_fail_closed(self) -> None:
        """Verify the `test_identity_and_reachability_fail_closed` behavior
        and its expected invariants."""
        a = ProvenanceNode("policy", "policy", "a" * 64, "policy:1")
        b = ProvenanceNode("bundle", "bundle", "b" * 64, "bundle:1", ("policy",))
        graph = ProvenanceGraph((a, b), (("bundle", "policy"),))
        proof = build_integrity_proof(
            graph,
            identities={"policy": "wrong"},
            reachable_pairs=(("bundle", "missing"),),
        )
        self.assertFalse(proof.verified)
        self.assertFalse(proof.required_identities_verified)

    def test_file_digest_is_verified(self) -> None:
        """Verify the `test_file_digest_is_verified` behavior
        and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "artifact.txt"
            artifact.write_text("hello", encoding="utf-8")
            digest = sha256(artifact.read_bytes()).hexdigest()
            graph_file = root / "graph.json"
            graph_file.write_text(
                json.dumps(
                    {
                        "nodes": [
                            {
                                "node_id": "artifact",
                                "kind": "artifact",
                                "digest": digest,
                                "identity": "artifact:1",
                                "path": "artifact.txt",
                                "derived_from": [],
                            }
                        ],
                        "required_edges": [],
                    }
                ),
                encoding="utf-8",
            )
            proof = verify_provenance_graph(graph_file)
            self.assertTrue(proof.verified)
            artifact.write_text("tampered", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatches"):
                verify_provenance_graph(graph_file)

    def test_graph_serialization_binds_digest(self) -> None:
        """Verify the `test_graph_serialization_binds_digest` behavior
        and its expected invariants."""
        a = ProvenanceNode("policy", "policy", "a" * 64, "policy:1")
        graph = ProvenanceGraph((a,))
        payload = graph.to_dict()
        loaded = load_provenance_graph_from_payload(payload)
        self.assertEqual(graph.graph_digest(), loaded.graph_digest())


def load_provenance_graph_from_payload(payload: dict[str, Any]) -> ProvenanceGraph:
    """Verify the `load_provenance_graph_from_payload` behavior
    and its expected invariants."""
    raw_nodes = [
        ProvenanceNode(
            node_id=item["node_id"],
            kind=item["kind"],
            digest=item["digest"],
            identity=item["identity"],
            derived_from=tuple(item["derived_from"]),
            path=item.get("path"),
        )
        for item in payload["nodes"]
    ]
    return ProvenanceGraph(
        tuple(raw_nodes), tuple(tuple(edge) for edge in payload["required_edges"])
    )
