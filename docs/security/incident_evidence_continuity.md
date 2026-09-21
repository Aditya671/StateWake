# Tier 14 — Security Incident Evidence & Forensic Continuity

## Scope

Tier 14 provides a bounded evidence model for reconstructing security incidents that affect StateWake trust or reliability state. It does not make StateWake an enterprise incident-response platform.

## Invariants

```text
Detect
 ↓
Preserve
 ↓
Contain
 ↓
Assess
 ↓
Recover
 ↓
Re-verify
```

A security incident remains distinct from an ordinary reliability discrepancy. Timestamps establish observation context; they do not establish causality.

## Evidence contract

Each incident records:

- deterministic incident and event identity;
- attributable actor context;
- preserved evidence references and digests;
- affected StateWake state and trust context;
- security-audit event digests without duplicating the audit stream;
- explicit uncertainty;
- optional key-compromise blast radius;
- recovery evidence bound to the incident;
- post-recovery verification evidence.

The incident store is a separate hash-linked JSONL chain. It stores references and metadata, not arbitrary incident payload copies.

## Recovery continuity

Recovery may not be treated as proof that the incident was harmless. A `reverified` incident requires an applied recovery record and verified post-recovery evidence drawn from the preserved incident evidence set.

Missing dependencies remain explicit. Reconstruction never infers causality and never silently converts absent evidence into a successful reconstruction.

## External incident systems

Export to an external incident-response or ticketing platform remains an integration boundary. StateWake owns only the minimum evidence needed to reconstruct its own security-relevant state transitions.
