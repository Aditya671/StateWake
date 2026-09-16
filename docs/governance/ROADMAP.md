# Roadmap

## Current position

**v0.1.1 — canonical Production/Stable baseline**

The historical phase sequence is implementation evidence, not a roadmap authority. The current product is governed by the V1 architecture in `docs/architecture/ARCHITECTURE.md` and the source architecture in `docs/architecture/ARCHITECTURE.md` and ADR 0003.

## V1 lifecycle

```text
execution
  → captured evidence
  → provenance / lineage
  → integrity
  → deterministic verification
  → reliability state
  → discrepancy detection
  → reconciliation / durable recovery
  → attestation / explainable decision
```

## Completed V1 consolidation

The verified `0.5.44`–`0.5.58` stream established the canonical evidence chain, external evidence receipt/admission, evidence-backed reliability state, outcome attestation and verification, portable proof, provenance/lineage closure, decision-basis binding, recovery binding, behavioral comparison, and discrepancy-to-reconciliation binding.

## Current release gate

Before declaring a public production release, the repository must pass the integration gate defined in `docs/governance/VERSIONING.md` and `docs/governance/RELEASE_READINESS.md`.

The package must work in two forms:

1. **Library integration** — a clean external Python project can import the stable public API and consume the reliability lifecycle without importing internal modules.
2. **Optional HTTP integration** — the WSGI adapter can expose verification capabilities without changing the framework-neutral core.

No new feature phase is automatically authorized by this release gate. If the gate fails because of a genuine V1 architecture gap, that gap becomes the sole basis for the next development phase.

## Historical implementation

Detailed historical phase records are retained in the `repository history` historical archive for reference. They are not active development instructions.
