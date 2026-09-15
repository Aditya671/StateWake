"""Deterministic V1 reliability-proof lineage closure contracts."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from statewake.utils.json_support import JsonValue, string_sequence

_HEX = set("0123456789abcdef")


def _canonical(payload: Mapping[str, JsonValue]) -> bytes:
    """Return the canonical representation used for deterministic identity and signing."""
    return json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _digest(value: str, field: str) -> None:
    """Return the deterministic digest for this domain value."""
    if len(value) != 64 or any(ch not in _HEX for ch in value):
        raise ValueError(f"{field} must be lowercase SHA-256 hex.")


@dataclass(frozen=True, slots=True)
class ReliabilityLineageBinding:
    """One reliability artifact bound to an exact provenance-graph node."""

    role: str
    node_id: str
    identity: str
    digest: str

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if (
            not self.role.strip()
            or not self.node_id.strip()
            or not self.identity.strip()
        ):
            raise ValueError(
                "lineage binding role, node_id, and identity must not be empty."
            )
        _digest(self.digest, "digest")

    def to_dict(self) -> dict[str, str]:
        """Serialize this object to its canonical dictionary representation."""
        return {
            "role": self.role,
            "node_id": self.node_id,
            "identity": self.identity,
            "digest": self.digest,
        }


@dataclass(frozen=True, slots=True)
class ReliabilityLineageClosure:
    """Portable proof that every material V1 input is connected to the declared run lineage."""

    format_version: str
    provenance_graph_digest: str
    run_role: str
    bindings: tuple[ReliabilityLineageBinding, ...]
    reachable_roles: tuple[str, ...]
    digest: str = ""

    def __post_init__(self) -> None:
        """Validate and normalize the initialized object state."""
        if self.format_version != "1":
            raise ValueError("unsupported reliability lineage closure format version.")
        _digest(self.provenance_graph_digest, "provenance_graph_digest")
        if self.run_role != "run":
            raise ValueError("lineage run_role must be 'run'.")
        if not self.bindings:
            raise ValueError("lineage closure requires bindings.")
        roles = [item.role for item in self.bindings]
        if len(roles) != len(set(roles)):
            raise ValueError("lineage binding roles must be unique.")
        nodes = [item.node_id for item in self.bindings]
        if len(nodes) != len(set(nodes)):
            raise ValueError("lineage binding node IDs must be unique.")
        if "run" not in roles:
            raise ValueError("lineage closure must bind a run node.")
        if any(role not in roles for role in self.reachable_roles):
            raise ValueError("reachable lineage roles must have bindings.")
        computed = self.computed_digest()
        if self.digest and self.digest != computed:
            raise ValueError("reliability lineage closure digest mismatch.")
        object.__setattr__(self, "digest", computed)

    def payload(self) -> dict[str, Any]:
        """Return the canonical payload represented by this object."""
        return {
            "format_version": self.format_version,
            "provenance_graph_digest": self.provenance_graph_digest,
            "run_role": self.run_role,
            "bindings": [item.to_dict() for item in self.bindings],
            "reachable_roles": list(self.reachable_roles),
        }

    def computed_digest(self) -> str:
        """Digest computed from the canonical payload."""
        return sha256(_canonical(self.payload())).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize this object to its canonical dictionary representation."""
        return {**self.payload(), "digest": self.digest}

    @classmethod
    def from_dict(cls, payload: Mapping[str, JsonValue]) -> ReliabilityLineageClosure:
        """Construct this object from its serialized dictionary representation."""
        raw_bindings = payload.get("bindings", [])
        if not isinstance(raw_bindings, list):
            raise ValueError("bindings must be a JSON array.")
        bindings_list: list[ReliabilityLineageBinding] = []
        for item in raw_bindings:
            if not isinstance(item, Mapping):
                raise ValueError("each lineage binding must be a JSON object.")
            bindings_list.append(
                ReliabilityLineageBinding(
                    role=str(item["role"]),
                    node_id=str(item["node_id"]),
                    identity=str(item["identity"]),
                    digest=str(item["digest"]),
                )
            )
        bindings = tuple(bindings_list)
        return cls(
            format_version=str(payload["format_version"]),
            provenance_graph_digest=str(payload["provenance_graph_digest"]),
            run_role=str(payload.get("run_role", "run")),
            bindings=bindings,
            reachable_roles=string_sequence(
                payload.get("reachable_roles", []), field="reachable_roles"
            ),
            digest=str(payload.get("digest", "")),
        )
