# Data and Proof

StateWake's reliability claims are designed to be inspectable.

## Identity

Artifacts, evidence chains, state transitions, comparisons, reconciliation results, and attestations carry stable identifiers and deterministic digests where required by their lifecycle.

## Integrity

Verification recomputes the relevant representation and checks that the current artifact agrees with the recorded identity and digest.

## Completeness

Portable proof verification checks that required supporting artifacts and relationships are present rather than accepting a claim that only contains a headline result.

## Portability

Proof bundles can be transferred to another environment and verified from their packaged evidence context. The verifier should not need access to the original process that created the claim.

## Trust boundaries

A successful verification means that the defined invariants hold for the supplied evidence. It does not mean that every external system or model is universally correct. The scope of each reliability claim remains the scope of its evidence and verification rules.
