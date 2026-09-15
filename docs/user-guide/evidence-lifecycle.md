# Evidence Lifecycle

StateWake's V1 lifecycle is centered on verifiable evidence.

## 1. Evidence admission

External evidence enters StateWake through an explicit receipt boundary. The receipt binds the expected artifact identity and producer context to the actual artifact and persisted receipt.

## 2. Evidence chain

Authoritative evidence references are composed into a `ReliabilityEvidenceChain`. StateWake records enough identity and digest information to verify that the referenced sources have not silently changed.

## 3. Provenance and lineage

Evidence is connected to its producers and upstream sources. Provenance is part of the reliability claim rather than an optional visualization.

## 4. Verification

Verification checks deterministic invariants such as identity, digest, expected source, receipt, state history, and proof completeness.

## 5. State

Verified evidence can support an authoritative reliability-state transition. State history is retained so a current state can be explained from its prior transitions.

## 6. Comparison

When before/after evidence exists, StateWake can bind a deterministic behavioral comparison to its exact input sources and evidence chain.

## 7. Reconciliation and recovery

A discrepancy can be bound to an exact reconciliation or recovery result. This prevents a later success from being presented as if it automatically explained an earlier discrepancy.

## 8. Attestation and decision

A verified lifecycle can produce an independently consumable attestation and decision basis. The attestation is evidence-backed rather than a standalone score.
