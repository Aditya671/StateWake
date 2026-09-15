# Golden Application C — Municipal / Decision Reliability

## Architecture

```text
synthetic service request
          |
          v
 classification / rules producer
          |
          v
  StateWakeClient.ingest_bytes
          |
          v
 evidence + policy/model state
          |
          v
 behavioral comparison
          |
          v
 degraded / review outcome
```

## Evidence model

The synthetic producer emits a service-request classification, priority, policy version, and routing result. StateWake records the producer evidence and the resulting reliability claim.

## State transition

`unknown -> degraded` with a `review` decision. A policy/model-version change is compared explicitly and does not silently become an `accept` result.

## Failure catalog

1. A policy-version change produces a behavioral comparison requiring operator review.
2. The resulting state is `degraded` rather than silently asserting equivalence.
3. Evidence is deliberately tampered with after proof creation; verification rejects it.

## Expected output

The command prints JSON with `chain_verified`, `outcome_verified`, `proof_bundle_verified`, and `tamper_rejected` all set to `true`, with the injected failure describing the degraded/review outcome.

## Security notes

All requests and decisions are synthetic. No citizen record, personally identifiable information, government system, or real policy is accessed.

## Limitations

This is not an actual municipal policy or eligibility engine. StateWake does not make the civic decision; it records and verifies the evidence supporting the reliability claim.

## Run and test

```bash
PYTHONPATH=src:. python docs/examples/golden/municipal_decision_reliability.py
pytest -q tests/integration/golden/test_golden_applications.py -p no:ddtrace -p no:anyio -p no:pytest_asyncio
```
