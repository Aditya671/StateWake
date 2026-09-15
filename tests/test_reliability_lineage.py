"""Regression tests for StateWake.

The active test suite protects the public package behavior and integration boundaries.
"""

# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportUnknownParameterType=false
# pyright: reportMissingParameterType=false
from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

from statewake.domain.provenance import ProvenanceGraph, ProvenanceNode
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.domain.reliability_lineage import ReliabilityLineageClosure
from statewake.services.reliability_lineage_service import (
    build_reliability_lineage_closure,
    verify_reliability_lineage_closure,
)


def _write(root: Path, name: str, payload: object) -> Path:
    """Verify the `_write` behavior and its expected invariants."""
    path = root / name
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def _ref(root: Path, kind: str, identity: str, name: str) -> EvidenceReference:
    """Verify the `_ref` behavior and its expected invariants."""
    path = root / name
    return EvidenceReference(
        kind, identity, sha256(path.read_bytes()).hexdigest(), name
    )


def _graph(
    root: Path,
    refs: dict[str, EvidenceReference],
    *,
    edges: tuple[tuple[str, str], ...] | None = None,
) -> None:
    """Verify the `_graph` behavior and its expected invariants."""
    nodes = tuple(
        ProvenanceNode(
            node_id=role.replace(":", "-"),
            kind=ref.kind,
            digest=ref.digest,
            identity=ref.identity,
            derived_from=(),
        )
        for role, ref in refs.items()
    )
    if edges is None:
        edges = tuple((role.replace(":", "-"), "run") for role in refs if role != "run")
    parents = {role: [] for role in refs}
    for child, parent in edges:
        parents[child].append(parent.replace(":", "-"))
    nodes = tuple(
        ProvenanceNode(
            n.node_id, n.kind, n.digest, n.identity, tuple(parents.get(role, []))
        )
        for role, n in ((role, node) for role, node in zip(refs, nodes, strict=True))
    )
    normalized_edges = tuple(
        (child.replace(":", "-"), parent.replace(":", "-")) for child, parent in edges
    )
    graph = ProvenanceGraph(nodes, normalized_edges)
    (root / "provenance.json").write_text(
        json.dumps(graph.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


class ReliabilityLineageTests(unittest.TestCase):
    """Provide regression coverage for the ReliabilityLineageTests behavior."""

    def _chain(
        self, root: Path, *, with_basis: bool = False
    ) -> ReliabilityEvidenceChain:
        """Verify the `_chain` behavior and its expected invariants."""
        _write(root, "run.json", {"run": "r"})
        _write(root, "state.json", {"state": "reliable"})
        _write(root, "evidence.json", {"e": "1"})
        _write(root, "integrity.json", {"verified": True})
        refs = {
            "run": _ref(root, "run", "run-1", "run.json"),
            "state": _ref(root, "state", "state-1", "state.json"),
            "evidence:0": _ref(root, "evidence", "e1", "evidence.json"),
        }
        basis_ref = None
        if with_basis:
            basis = {
                "format_version": "1",
                "basis_type": "manual",
                "basis_id": "basis-1",
                "version": "1",
                "decision": "accept",
                "reliability_state": "reliable",
                "rationale": ["ok"],
                "input_digests": [refs["evidence:0"].digest],
                "policy_id": None,
                "policy_version": None,
                "policy_digest": None,
            }
            basis_payload = dict(basis)
            basis_payload["digest"] = sha256(
                json.dumps(
                    basis, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode()
            ).hexdigest()
            _write(root, "basis.json", basis_payload)
            basis_ref = _ref(root, "decision-basis", "basis-1", "basis.json")
            refs["decision_basis"] = basis_ref
        edges = [("state", "run"), ("evidence:0", "run")]
        if with_basis:
            edges.append(("decision_basis", "evidence-0"))
        _graph(root, refs, edges=tuple(edges))
        provenance = root / "provenance.json"
        return ReliabilityEvidenceChain(
            chain_id="chain-1",
            run=refs["run"],
            state=refs["state"],
            evidence=(refs["evidence:0"],),
            provenance=EvidenceReference(
                "provenance",
                "p1",
                sha256(provenance.read_bytes()).hexdigest(),
                provenance.name,
            ),
            integrity=_ref(root, "integrity", "integrity-1", "integrity.json"),
            verification_status="verified",
            reliability_state="reliable",
            reconciliation_state="verified",
            decision="accept",
            decision_rationale=("ok",),
            decision_basis_ref=basis_ref,
        )

    def test_complete_lineage_closure_round_trip(self):
        """Verify the `test_complete_lineage_closure_round_trip` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chain = self._chain(root, with_basis=True)
            closure = build_reliability_lineage_closure(chain, root=root)
            self.assertEqual(
                closure.provenance_graph_digest,
                __import__(
                    "statewake.services.provenance_service",
                    fromlist=["load_provenance_graph"],
                )
                .load_provenance_graph(root / "provenance.json")
                .graph_digest(),
            )
            self.assertIn("decision_basis", closure.reachable_roles)
            self.assertEqual(
                closure,
                verify_reliability_lineage_closure(chain, root=root, closure=closure),
            )
            self.assertEqual(
                closure, ReliabilityLineageClosure.from_dict(closure.to_dict())
            )

    def test_missing_material_node_fails_closed(self):
        """Verify the `test_missing_material_node_fails_closed` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chain = self._chain(root)
            payload = json.loads((root / "provenance.json").read_text())
            payload["nodes"] = [
                node for node in payload["nodes"] if node["node_id"] != "evidence-0"
            ]
            payload.pop("graph_digest", None)
            payload["graph_digest"] = sha256(
                json.dumps(
                    {
                        "nodes": sorted(payload["nodes"], key=lambda x: x["node_id"]),
                        "required_edges": payload["required_edges"],
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode()
            ).hexdigest()
            (root / "provenance.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n"
            )
            tampered = replace(
                chain,
                provenance=EvidenceReference(
                    "provenance",
                    "p1",
                    sha256((root / "provenance.json").read_bytes()).hexdigest(),
                    "provenance.json",
                ),
            )
            with self.assertRaisesRegex(
                ValueError, "not found|required provenance edges"
            ):
                build_reliability_lineage_closure(tampered, root=root)

    def test_disconnected_lineage_fails_closed(self):
        """Verify the `test_disconnected_lineage_fails_closed` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chain = self._chain(root)
            refs = {
                "run": chain.run,
                "state": chain.state,
                "evidence:0": chain.evidence[0],
            }
            _graph(root, refs, edges=(("state", "run"),))
            bad = replace(
                chain,
                provenance=EvidenceReference(
                    "provenance",
                    "p1",
                    sha256((root / "provenance.json").read_bytes()).hexdigest(),
                    "provenance.json",
                ),
            )
            with self.assertRaisesRegex(
                ValueError, "required provenance edges|not found|not connected"
            ):
                build_reliability_lineage_closure(bad, root=root)

    def test_basis_must_derive_from_declared_input(self):
        """Verify the `test_basis_must_derive_from_declared_input` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chain = self._chain(root, with_basis=True)
            refs = {
                "run": chain.run,
                "state": chain.state,
                "evidence:0": chain.evidence[0],
                "decision_basis": chain.decision_basis_ref,
            }
            _graph(
                root,
                refs,  # type: ignore
                edges=(
                    ("state", "run"),
                    ("evidence:0", "run"),
                    ("decision_basis", "run"),
                ),
            )
            bad = replace(
                chain,
                provenance=EvidenceReference(
                    "provenance",
                    "p1",
                    sha256((root / "provenance.json").read_bytes()).hexdigest(),
                    "provenance.json",
                ),
            )
            with self.assertRaisesRegex(ValueError, "decision-basis lineage"):
                build_reliability_lineage_closure(bad, root=root)

    def test_lineage_closure_detects_provenance_digest_tampering(self):
        """Verify the `test_lineage_closure_detects_provenance_digest_tampering` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chain = self._chain(root)
            closure = build_reliability_lineage_closure(chain, root=root)
            payload = json.loads((root / "provenance.json").read_text())
            payload["nodes"][0]["identity"] = "tampered"
            payload.pop("graph_digest", None)
            payload["graph_digest"] = sha256(
                json.dumps(
                    {
                        "nodes": sorted(payload["nodes"], key=lambda x: x["node_id"]),
                        "required_edges": payload["required_edges"],
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode()
            ).hexdigest()
            (root / "provenance.json").write_text(
                json.dumps(payload, indent=2, sort_keys=True) + "\n"
            )
            tampered = replace(
                chain,
                provenance=EvidenceReference(
                    "provenance",
                    "p1",
                    sha256((root / "provenance.json").read_bytes()).hexdigest(),
                    "provenance.json",
                ),
            )
            with self.assertRaisesRegex(ValueError, "does not match|not found"):
                verify_reliability_lineage_closure(tampered, root=root, closure=closure)

    def test_duplicate_identity_is_ambiguous(self):
        """Verify the `test_duplicate_identity_is_ambiguous` behavior and its expected invariants."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            chain = self._chain(root)
            nodes = (
                ProvenanceNode("run", "run", chain.run.digest, chain.run.identity),
                ProvenanceNode(
                    "state", "state", chain.state.digest, chain.state.identity, ("run",)
                ),
                ProvenanceNode(
                    "evidence-0",
                    "evidence",
                    chain.evidence[0].digest,
                    chain.evidence[0].identity,
                    ("run",),
                ),
                ProvenanceNode(
                    "evidence-duplicate",
                    "evidence",
                    chain.evidence[0].digest,
                    chain.evidence[0].identity,
                    ("run",),
                ),
            )
            graph = ProvenanceGraph(
                nodes,
                (
                    ("state", "run"),
                    ("evidence-0", "run"),
                    ("evidence-duplicate", "run"),
                ),
            )
            (root / "provenance.json").write_text(
                json.dumps(graph.to_dict(), indent=2, sort_keys=True) + "\n"
            )
            bad = replace(
                chain,
                provenance=EvidenceReference(
                    "provenance",
                    "p1",
                    sha256((root / "provenance.json").read_bytes()).hexdigest(),
                    "provenance.json",
                ),
            )
            with self.assertRaisesRegex(ValueError, "ambiguous"):
                build_reliability_lineage_closure(bad, root=root)


if __name__ == "__main__":
    unittest.main()
