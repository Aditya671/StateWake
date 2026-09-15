# Architecture

StateWake has four principal layers:

```text
Consumer application
       │
       ▼
Stable public API / WSGI edge
       │
       ▼
Application services
       │
       ▼
Domain primitives + authoritative stores/adapters
```

## Domain

Domain objects model evidence, provenance, reliability state, comparisons, reconciliation, recovery, and attestations.

## Services

Services implement deterministic lifecycle operations and verification rules. They are not intended to become a second public API surface.

## Adapters

Adapters connect StateWake to storage, runtime evidence, attestations, operational indexes, and other external boundaries.

## Evidence producers

Existing evaluation, testing, replay, telemetry, and runtime systems can remain authoritative producers. StateWake consumes their evidence through explicit boundaries rather than absorbing their entire product responsibilities.

## Legacy boundary

Historical implementations that do not belong to the V1 product are retained in the `repository history` historical archive for reference only. They are not active runtime dependencies and must not become accidental public API.

## Architecture principle

The architecture is organized around the chain:

**verifiable evidence → trustworthy provenance → verified state → explainable decision → durable recovery**
