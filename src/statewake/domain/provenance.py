"""Cross-artifact provenance graphs and end-to-end integrity proofs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any


def _canonical(payload: Any) -> bytes:
    """Return the canonical representation used for deterministic identity and signing."""
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(value: str) -> bool:
    """Return the SHA-256 digest of the supplied canonical bytes."""
    return len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


@dataclass(frozen=True, slots=True)
class ProvenanceNode:
    """One immutable artifact node in a cross-artifact provenance graph."""

    node_id: str
    kind: str
    digest: str
    identity: str
    derived_from: tuple[str, ...] = ()
    path: str | None = None

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if (
            not self.node_id.strip()
            or not self.kind.strip()
            or not self.identity.strip()
        ):
            raise ValueError("node_id, kind, and identity must not be empty.")
        if not _sha256(self.digest):
            raise ValueError("digest must be lowercase SHA-256 hex.")
        if self.path is not None and (
            not self.path.strip()
            or self.path.startswith("/")
            or ".." in self.path.replace("\\", "/").split("/")
        ):
            raise ValueError("path must be relative and must not contain '..'.")
        if any(not value.strip() for value in self.derived_from):
            raise ValueError("derived_from must not contain blank values.")
        if self.node_id in self.derived_from:
            raise ValueError("a provenance node cannot derive from itself.")

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "digest": self.digest,
            "identity": self.identity,
            "derived_from": list(self.derived_from),
            "path": self.path,
        }


@dataclass(frozen=True, slots=True)
class ProvenanceGraph:
    """Immutable graph with deterministic identity and explicit integrity checks."""

    nodes: tuple[ProvenanceNode, ...]
    required_edges: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        ids = [node.node_id for node in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("provenance node IDs must be unique.")
        known = set(ids)
        for node in self.nodes:
            unknown = [source for source in node.derived_from if source not in known]
            if unknown:
                raise ValueError(
                    f"node {node.node_id!r} references unknown provenance: {', '.join(unknown)}"
                )
        for child, parent in self.required_edges:
            if child not in known or parent not in known:
                raise ValueError(
                    "required provenance edges must reference known node IDs."
                )

    def node(self, node_id: str) -> ProvenanceNode:
        """Return the provenance node identified by the supplied identity."""
        for node in self.nodes:
            if node.node_id == node_id:
                return node
        raise KeyError(node_id)

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            "nodes": [
                node.to_dict()
                for node in sorted(self.nodes, key=lambda item: item.node_id)
            ],
            "required_edges": [list(edge) for edge in sorted(self.required_edges)],
        }

    def graph_digest(self) -> str:
        """Return the deterministic digest of the provenance graph."""
        return sha256(_canonical(self.payload())).hexdigest()

    def roots(self) -> tuple[str, ...]:
        """Return provenance nodes that have no incoming dependency edges."""
        referenced = {parent for node in self.nodes for parent in node.derived_from}
        return tuple(
            sorted(
                node.node_id for node in self.nodes if node.node_id not in referenced
            )
        )

    def children(self, node_id: str) -> tuple[str, ...]:
        """Return the direct provenance children of a node."""
        return tuple(
            sorted(node.node_id for node in self.nodes if node_id in node.derived_from)
        )

    def validate_acyclic(self) -> None:
        """Validate that the provenance graph contains no cycles."""
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node_id: str) -> None:
            """Visit a provenance node while checking for cycles and recording traversal state."""
            if node_id in visiting:
                raise ValueError("provenance graph cycle detected.")
            if node_id in visited:
                return
            visiting.add(node_id)
            for parent in self.node(node_id).derived_from:
                visit(parent)
            visiting.remove(node_id)
            visited.add(node_id)

        for node in self.nodes:
            visit(node.node_id)

    def validate_required_edges(self) -> None:
        """Validate that all required provenance relationships are present."""
        self.validate_acyclic()
        edges = {
            (node.node_id, parent)
            for node in self.nodes
            for parent in node.derived_from
        }
        missing = [edge for edge in self.required_edges if edge not in edges]
        if missing:
            formatted = ", ".join(f"{child}->{parent}" for child, parent in missing)
            raise ValueError(f"required provenance edges are missing: {formatted}")

    def verify_identities(self, identities: Mapping[str, str]) -> None:
        """Verify that provenance identities and references are internally consistent."""
        mismatches = []
        for node_id, expected in identities.items():
            actual = self.node(node_id).identity
            if actual != expected:
                mismatches.append(f"{node_id}: expected {expected!r}, got {actual!r}")  # type: ignore
        if mismatches:
            raise ValueError("provenance identity mismatches: " + "; ".join(mismatches))  # type: ignore

    def reachable(self, start_id: str, target_id: str) -> bool:
        """Return the nodes reachable from the supplied provenance roots."""
        self.node(start_id)
        self.node(target_id)
        seen: set[str] = set()
        stack = [start_id]
        while stack:
            current = stack.pop()
            if current == target_id:
                return True
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self.node(current).derived_from)
        return False

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        self.validate_required_edges()
        return {
            "graph_digest": self.graph_digest(),
            **self.payload(),
            "roots": list(self.roots()),
        }


@dataclass(frozen=True, slots=True)
class IntegrityProof:
    """Machine-verifiable result for one cross-artifact provenance graph."""

    graph_digest: str
    required_edges_verified: bool
    required_identities_verified: bool
    reachable_pairs: tuple[tuple[str, str, bool], ...]
    verified: bool

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if not _sha256(self.graph_digest):
            raise ValueError("graph_digest must be lowercase SHA-256 hex.")

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {
            "graph_digest": self.graph_digest,
            "required_edges_verified": self.required_edges_verified,
            "required_identities_verified": self.required_identities_verified,
            "reachable_pairs": [list(item) for item in self.reachable_pairs],
            "verified": self.verified,
        }
