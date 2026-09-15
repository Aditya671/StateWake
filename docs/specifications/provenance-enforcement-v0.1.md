> **Specification classification:** Active V1 specification.
>

# Provenance-Aware Operational Inspection + Integrity Enforcement v0.1

## Purpose

Make cross-artifact provenance integrity a prerequisite for normal operational use of a bundle.

## Rules

1. A verified operational bundle must yield a deterministic provenance graph.
2. The bundle node digest must equal the exact bundle file SHA-256.
3. Each artifact node identity/kind/digest must match the verified bundle artifact.
4. The graph must be acyclic, satisfy required edges, and reach every bundle artifact.
5. If a provenance sidecar exists or is explicitly supplied, its graph payload must equal the freshly derived graph.
6. An indexed provenance digest must match its current sidecar bytes.
7. Verification failures are fail-closed for inspection, indexing, lifecycle eligibility, and API responses.
8. No new provenance storage model is introduced; the existing graph remains authoritative.
