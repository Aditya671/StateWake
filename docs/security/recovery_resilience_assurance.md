# Tier 6 — Recovery & Resilience Assurance

## Status

This document defines the StateWake Tier 6 recovery and resilience assurance mechanism. It does not itself provide a high-availability guarantee or deployment recovery service.

## Purpose

Tier 6 composes the existing StateWake evidence, provenance, durable-state, trust-checkpoint, key-lifecycle, reconciliation, and recovery primitives into executable assurance for security-sensitive failure and recovery paths.

The verified recovery chain is:

```text
Detect
  ↓
Contain
  ↓
Identify authoritative evidence
  ↓
Recover
  ↓
Re-verify
  ↓
Re-attest if justified
  ↓
Expose residual uncertainty
```

Recovery restores the strongest state justified by authoritative evidence. It must never manufacture missing trust.

## Existing capabilities reused

Tier 6 does not introduce a parallel recovery subsystem. It reuses:

| Existing capability | Existing implementation |
|---|---|
| Evidence integrity | evidence references and digest verification |
| Provenance integrity | `ProvenanceGraph.validate_required_edges()` and identity verification |
| Durable state integrity | hash-linked JSONL/transactional SQLite state stores |
| Atomic persistence | `atomic_write_bytes()` / `atomic_write_text()` |
| Trust checkpoints | `TrustCheckpoint`, `compare_local_tip()`, independent verification |
| Signing-key lifecycle | `ExternalSigningAdapter.rotate()` / `.revoke()` |
| Reconciliation binding | existing reconciliation binding service |
| Recovery-result binding | `verify_reliability_recovery_outcome()` |
| Failure observability | `ReliabilityFailureHook` |

## Recovery authority hierarchy

Recovery decisions use this descending authority order:

```text
Independent trusted source
        ↓
Verified canonical evidence
        ↓
Validated durable state
        ↓
Derived local views
        ↓
Caches / transient observations
```

A lower-confidence representation must not silently overwrite a higher-confidence source.

## Deterministic recovery modes

### Mode A — Evidence corruption

Detect digest mismatch → invalidate affected artifact → locate authoritative replacement → recompute digest → re-verify provenance/evidence → restore only after verification.

### Mode B — Provenance corruption

Detect broken graph → quarantine affected relationship/state → reconstruct only from authoritative records → verify graph and identities.

### Mode C — State-history corruption

Detect invalid history → identify the last independently verified state/checkpoint → recover only to that justified point → rebuild derived state → verify the resulting history.

### Mode D — Trust-checkpoint disagreement

Detect local-tip disagreement → classify as security discrepancy → preserve both observations → do not silently select a branch → investigate/reconcile from the authoritative source.

### Mode E — Signing-key compromise

Revoke affected key → identify affected trust material → preserve historical evidence → rotate/re-establish replacement trust → re-attest only evidence that remains independently verifiable.

## Recovery non-invention invariant

Recovery must not:

- generate a missing evidence record because another artifact references it;
- accept an unsigned object because a prior object was signed;
- silently select one conflicting history branch;
- reconstruct sensitive metadata from assumptions;
- replace a failed security control with a weaker unverified path.

## Tier 6 verification evidence

`scripts/security/verify_recovery_resilience.py` is the deterministic evidence-consistency verifier. It checks that the Tier 6 document, operational recovery contract, Tier 5 assurance boundary, and executable Tier 6 regression suite consistently represent the required recovery semantics.

The executable suite then failure-injects the existing recovery primitives for corruption, provenance damage, state-history damage, checkpoint disagreement, key compromise response, interrupted/partial recovery, and mandatory post-recovery verification.

## Exit condition

Tier 6 is complete when executable evidence demonstrates that:

- security failures are detected;
- affected state is contained rather than silently accepted;
- recovery follows explicit authority rules;
- recovery does not fabricate trust;
- post-recovery verification is mandatory;
- trust status is clearly exposed.

## Boundaries and residual risk

Tier 6 does not establish host-OS recovery, storage-provider disaster recovery, KMS/HSM availability, external producer correctness, network availability, high availability, or automatic operational remediation. Deployment owners remain responsible for those boundaries.

Independent verification in this project means execution from a fresh clean copy by a separate verification run of the candidate. It is not an external human security audit or penetration test.

## Relationship to package release

Tier 6 describes recovery and resilience controls in the v0.4.0 package. It does not itself perform release tagging or publication, and it does not replace deployment-specific recovery services.
