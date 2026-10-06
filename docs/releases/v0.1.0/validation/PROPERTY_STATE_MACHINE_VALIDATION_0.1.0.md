# Property and State-Machine Verification — 2026-09-13

## Scope

The property/state-machine harness adds a deterministic, dependency-free generated verification harness over the existing StateWake domain contracts. It does not replace the existing unit, integration, chaos, or failure-laboratory suites.

The harness covers:

1. transition serialization round trips;
2. transition digest binding under generated single-field mutations;
3. evidence-manifest round trips over generated evidence sets;
4. event-envelope round trips over generated event values;
5. reliability-state-machine exploration using valid and deliberately invalid transition choices.

## Reproducibility

- Seed: `20260913`
- Property cases: `250` per property
- State-machine cases: `250`
- State-machine steps per case: `40`
- Generated state-machine steps: `10,000`

The harness reports the seed and case index for a failure so a failing generated case can be reproduced. The generated campaign is deterministic and intentionally dependency-free because the current offline build environment does not contain Hypothesis.

## Invariants

The campaign requires that:

- every generated valid transition belongs to `ALLOWED_TRANSITIONS`;
- transition serialization/deserialization is identity-preserving;
- transition digests bind their serialized payload;
- single-field mutations are rejected;
- evidence manifests preserve generated item identity and metadata;
- event envelopes preserve canonical values;
- invalid state transitions are rejected without changing the modeled state;
- valid state-machine steps preserve predecessor digest linkage.

## Boundary

This harness is test infrastructure under `scripts/`; it is not part of the runtime StateWake reliability authority and is not exposed as a product API.

## Verification

The canonical sandbox run completed:

```text
5 generated properties passed
250 cases/property
250 state-machine cases × 40 steps = 10,000 generated state-machine steps
```

The complete regression suite also passed after integration.
