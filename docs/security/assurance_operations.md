# Tier 10 — Assurance Operations & Security Decision Automation

## Status

This is a **development assurance** artifact. It is not a release approval, certification, production-readiness approval, or publication authorization.

## Objective

Tier 10 maintains evidence-backed assurance state by converting already-verified StateWake evidence into deterministic, bounded operating decisions. It does not become a SIEM, SOAR, incident-response platform, threat-intelligence system, endpoint product, or IAM platform.

## Reused capabilities

Tier 10 reuses the existing reliability evidence chain, claim profiles, decision basis, state transitions, recovery outcomes, attestations, portable proof verification, operational hooks, and trust-domain lifecycle. No second evidence or decision-state architecture is introduced.

## Deterministic decision contract

`evaluate_assurance_decision()` maps explicit reliability state, verification result, trust status, recovery requirement, evidence references, verification results, and residual risk to one of the bounded decision classes:

- `ALLOW`
- `ALLOW_WITH_LIMITATIONS`
- `REQUIRE_REVERIFICATION`
- `QUARANTINE`
- `REJECT`
- `REVOKE_TRUST`
- `RECOVERY_REQUIRED`

These are operational outcomes, not scores or rankings.

The decision stores the evidence references, verification results, policy identity, deterministic rationale, timestamp/context, source state, source verification status, residual risk, and a content digest.

## Human override boundary

An operating exception is represented separately through `AssuranceException`. It preserves the underlying system assurance state and therefore cannot turn a failed invariant into a verified state. The exception records the unsatisfied invariant, continuation rationale, authorization, expiry, compensating control, required re-verification, and evidence references.

## Decision rules

The policy is intentionally deterministic:

- revoked trust → `REVOKE_TRUST`;
- recovery required → `RECOVERY_REQUIRED`;
- tampered portable evidence → `QUARANTINE`;
- invalid/incomplete evidence → `REJECT`;
- unverified or unavailable trust anchor → `REQUIRE_REVERIFICATION`;
- unreliable state → `REJECT`;
- degraded state or verification limitations → `ALLOW_WITH_LIMITATIONS`;
- verified reliable/recovered state → `ALLOW`.

## Exit condition

Tier 10 is satisfied for the development candidate when StateWake can maintain bounded, evidence-backed assurance decisions deterministically, preserve explanation and residual risk, represent operating exceptions without mutating system truth, and remain outside the scope of a generic enterprise security-operations platform.
