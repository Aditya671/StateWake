# ADR 0003 — Current StateWake Architecture

## Status
Accepted

## Context

StateWake evolved from an earlier reliability/change-management model. The active implementation no longer contains the historical `Contract` and `Regression` primitives described by ADR 0002. The current product is centered on a verifiable reliability-evidence lifecycle.

## Decision

The current StateWake architecture is a framework-neutral reliability-evidence infrastructure layer. `ReliabilityEvidenceChain` is the principal composition primitive. The lifecycle is:

```text
execution → captured evidence → provenance / lineage → integrity
→ deterministic verification → reliability state
→ discrepancy / comparison → reconciliation / durable recovery
→ attestation / explainable decision
```

Producer systems remain authoritative for their own execution, telemetry, orchestration, policy, and domain semantics. StateWake records and verifies evidence about those systems rather than replacing them.

The active layers are:

- **Domain:** typed models and invariants.
- **Services:** deterministic composition, verification, state, reconciliation, attestation, and proof workflows.
- **Adapters:** storage and producer/evidence boundaries.
- **Public API:** stable framework-neutral integration surface.
- **HTTP/CLI:** thin integration and operational boundaries over the same core services.

## Consequences

Historical orchestration, scheduling, watchdog, and generic control-plane concepts remain historical reference material and are not current StateWake runtime authorities. New features must extend existing evidence, verification, state, reconciliation, trust, or integration boundaries rather than introduce a competing authority.

This ADR supersedes ADR 0002 as the current domain-model authority while preserving ADR 0002 as historical decision provenance.
