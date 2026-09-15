> **Specification classification:** Active V1 specification.
>

# Cross-Artifact Provenance Model v0.1

## Purpose

Represent one deterministic provenance graph across already-produced reliability artifacts.

## Node

A `ProvenanceNode` identifies one artifact with:

- `node_id` — stable graph-local reference;
- `kind` — host-defined artifact kind;
- `identity` — exact semantic identity asserted by the host;
- `digest` — SHA-256 of the referenced bytes or canonical artifact representation;
- `derived_from` — explicit parent node references;
- optional relative `path` for byte-level verification.

## Graph invariants

- node IDs are unique;
- all references resolve;
- self references are rejected;
- cycles are rejected;
- required edges are explicit and must exist;
- asserted identities can be verified independently;
- referenced file bytes can be SHA-256 verified independently.

## Integrity proof

`IntegrityProof` records the graph digest, required-edge result, identity result, requested reachability
results, and final verification status. A graph is verified only when every requested check succeeds.

The graph does not infer semantic correctness from an artifact kind. Identity and lineage are explicit host
assertions so the domain remains deterministic and vendor-neutral.
