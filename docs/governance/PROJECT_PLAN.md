# Project Plan

## Current objective

StateWake's current objective is to maintain a coherent, verifiable reliability infrastructure layer for AI systems.

The governing lifecycle is:

```text
execution → evidence → provenance → integrity → verification
→ reliability state → discrepancy/comparison
→ reconciliation/recovery → attestation/decision
```

## Current baseline

**StateWake v0.1.0** is the locked public developer/package baseline.

The active product boundary is defined by `docs/architecture/ARCHITECTURE.md`. The public integration boundary is the `statewake` Python package plus the intentionally thin `statewake.server:app` WSGI adapter.

## Maintenance priorities

1. Preserve deterministic verification and evidence integrity.
2. Preserve provenance, lineage, and state-history explainability.
3. Preserve exact binding between discrepancies, comparisons, reconciliation, recovery, and attestations.
4. Keep the public Python API small and stable.
5. Keep framework and storage choices at adapter boundaries.
6. Keep release documentation complete and publishable as a web documentation set.
7. Derive any future capability from a demonstrated V1 architecture gap or adopter requirement.

## What is not automatically planned

No historical phase number authorizes new work. Historical orchestration, watchdog, scheduling, distributed-worker, and generic control-plane implementations remain in the `repository history` historical archive and are not current product commitments.

Likewise, testing, chaos, replay, regression, telemetry, and evaluation capabilities may remain useful evidence producers but are not the product's primary differentiation.

## Release discipline

Before a new release:

- run the complete verification suite;
- validate package/distribution/import/CLI identity;
- inspect the public API for accidental surface expansion;
- verify documentation and changelog consistency;
- build and install the release artifact in a clean environment; and
- perform an architecture-level release decision.

If the decision identifies a genuine V1 architecture gap, that specific gap becomes the basis for the next development cycle.

## Historical record

The detailed historical phase-by-phase implementation record is preserved in repository history and `repository history`. It is useful for provenance and engineering archaeology, but it is not an active roadmap.
