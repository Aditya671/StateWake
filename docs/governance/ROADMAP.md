# Roadmap

## Current position

**Current source: v0.5.0. Current published Production/Stable release: v0.4.1.**

The published release sequence records four deliberate boundaries: packaging stabilization at v0.1.1, cybersecurity completion at v0.2.0, Persistence & Dataset completion at v0.4.0, and the published v0.4.1 reliability/integration update. The v0.5.0 source line is the next candidate and is not yet a published release.

## Completed product progression

```text
v0.1.1  →  Production/Stable packaging promotion
v0.2.0  →  Cybersecurity progression through V3 Tier 15
v0.4.0  →  Persistence & Dataset Architecture through Tier 15
v0.4.1  →  Production/Stable reliability, integration, and assurance update
v0.5.0  →  Current source candidate; release/publication gates still pending
```

The underlying reliability lifecycle remains:

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

## Development boundary

The cybersecurity and persistence/dataset architecture roadmaps represented by the supplied design sources are complete at their respective Tier 15 boundaries. Future work should therefore be derived from an explicit architecture gap or adopter requirement rather than automatically inventing another tier sequence.

## Release gate

Before any future publication, run the repository release gates and external platform checks defined in `docs/governance/RELEASE_GOVERNANCE.md` and `docs/governance/RELEASE_CANDIDATE_PROTOCOL.md`.
