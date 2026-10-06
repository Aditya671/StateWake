# Reliability decision basis, reconciliation and lineage investigation

StateWake's read-only UI can inspect one configured `ReliabilityEvidenceChain` and reconstruct the already-recorded relationship among a reliability decision, its exact decision basis, discrepancy/reconciliation evidence, optional recovery evidence, and verified provenance lineage closure.

This is an **inspection capability**. It does not recompute a business decision, reconcile state, execute recovery, mutate an evidence chain, attest an outcome, or authorize a side effect.

## Configuration

Set the read API to one existing canonical chain file:

```text
STATEWAKE_UI_RELIABILITY_DECISION_CHAIN=<path-to-ReliabilityEvidenceChain-json>
```

The browser never supplies this path. The route is enabled only when the server is configured with it.

```text
GET /api/v1/decision-lineage
```

The response uses `decision-lineage-investigation.v1` and supports deterministic ETag/304 conditional reads. It accepts no browser query parameters.

## Authority chain

The projection is derived only after the existing StateWake authorities succeed:

```text
ReliabilityEvidenceChain
        ↓
verify_reliability_evidence_chain()
        ↓
verify_reliability_decision_basis()
        ↓
comparison / reconciliation binding verification when present
        ↓
recovery verification when the chain records recovered state
        ↓
build_reliability_lineage_closure()
        ↓
read-only presentation projection
```

The read side preflights the configured chain and every local artifact that the existing verifiers may read. It rejects symlink traversal, references outside the configured evidence root, missing files, oversized individual sources, and aggregate source-size overflow before verification begins.

## Decision input semantics

A decision basis binds the material evidence used to make the recorded reliability decision. Canonical generation binds:

- run state;
- reliability state;
- evidence artifacts;
- behavioral comparison when present;
- reconciliation evidence when present;
- recovery evidence when present.

It intentionally does **not** recursively bind the provenance graph or integrity file that contains/verifies the decision basis. Doing so creates an unsatisfiable digest cycle: the graph contains the basis node, the graph digest would change the basis, and the changed basis would change the graph again.

For compatibility, legacy/manual decision bases may contain provenance, integrity, or attestation digests. Those values remain verifiable as **verification context**. They are not promoted into provenance-graph nodes merely to satisfy the UI.

The operator projection therefore classifies inputs as:

```text
lineage-bound
verification-context
```

Lineage-bound inputs must be represented by the existing provenance graph and reachable to the recorded run. Verification-context inputs are shown with reachability as not applicable, not as a failed or invented lineage edge.

Unknown decision-basis digests still fail verification. The distinction is not a generic escape hatch for missing graph nodes.

## Reconciliation and recovery

Behavioral comparison, reconciliation binding, and recovery outcome are displayed separately because they prove different bounded claims:

```text
discrepancy observed
        ≠
reconciliation bound
        ≠
recovery recorded
        ≠
factual correctness
```

Existing deterministic comparison and reconciliation verifiers remain authoritative. A recovered chain must pass the existing recovery-outcome verifier. The read surface does not perform repair or infer that recovery made an external system correct.

## Lineage closure

The projection exposes the verified lineage graph/closure identity, material bindings, and run reachability. Existing cycle, edge, digest, identity, and reachability checks remain unchanged for graph-bindable inputs.

A verified lineage closure means StateWake can reconstruct the declared material dependency path for this recorded outcome. It does not prove the truth of external evidence or authorize a business action.

## Privacy and read-only boundary

The endpoint omits:

- local filesystem paths;
- raw evidence bytes;
- raw decision rationale;
- arbitrary metadata;
- external-system secrets;
- any write/reconciliation/recovery controls.

The UI shows rationale **counts** only. It does not send the raw rationale text to the browser.

## Failure behavior

The endpoint fails closed when the configured source is absent, invalid, tampered, symlinked, escapes the evidence root, exceeds configured byte bounds, or fails any existing decision/reconciliation/recovery/lineage verifier.

The browser exposes explicit unavailable, oversized, and invalid-source states rather than rendering a partial decision graph as verified.

## What this surface does not establish

A successful investigation does not by itself establish:

- factual correctness of the AI output;
- independent trust in an external producer;
- human approval;
- release/publication authorization;
- permission to execute a side effect;
- causal explanation beyond the relationships explicitly represented by StateWake evidence.
