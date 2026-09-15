# Architecture

## Product center

StateWake is a reliability-evidence infrastructure layer. Its authoritative lifecycle is:

```text
execution → captured evidence → provenance / lineage → integrity
→ deterministic verification → reliability state
→ discrepancy / comparison → reconciliation / durable recovery
→ attestation / explainable decision
```

`ReliabilityEvidenceChain` is the principal composition primitive. It references authoritative artifacts rather than duplicating external producer semantics.

## Layers

### Domain
Pure models and invariants. No network calls or vendor SDKs.

### Services
Deterministic application workflows for ingestion, composition, verification, state, reconciliation, attestation, provenance, and proof packaging.

### Adapters
Storage, runtime, telemetry, policy, attestation, and external-evidence integration boundaries. Adapters feed authoritative evidence into the lifecycle; they do not create a competing reliability authority.

### Public Python API
`statewake` exposes a deliberate consumer surface for evidence admission, evidence-chain construction/verification, outcome verification, and reliability-state reads. Internal service modules remain implementation details.

### HTTP adapter
`statewake.server:app` is a standard-library WSGI edge adapter. It delegates to the same framework-neutral services as the library and CLI. No HTTP framework is a core dependency.

### CLI
`statewake` is a thin operational interface. It is not the architecture authority.

## Integration model

```text
Host AI system / runtime / OTel / CI / evaluation tool
                     │
                     ▼
             Evidence adapter / receipt
                     │
                     ▼
          StateWake core
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
   Python API      CLI       Optional HTTP
```

The host system remains responsible for agent execution, telemetry collection, orchestration, scheduling, authentication, and external control planes. The engine establishes trustworthy evidence, verification, state, reconciliation, and decision provenance around those systems.

## Product boundary

The engine must not become a generic chaos platform, agent evaluator, observability dashboard, orchestration framework, distributed task queue, or self-referential watchdog system.
