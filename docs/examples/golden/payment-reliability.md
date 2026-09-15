# Golden Application A — Payment Reliability

## Architecture

```text
synthetic order/payment producer
            |
            v
     webhook occurrence
            |
            v
  WebhookEvidenceAdapter
            |
            v
 canonical evidence admission
            |
            v
 evidence chain -> state -> attestation -> proof
```

## Evidence model

The producer emits a synthetic webhook containing payment-event identity. `WebhookEvidenceAdapter` preserves request identity, content type, signature metadata, and delivery attempt without interpreting gateway business semantics.

## State transition

`unknown -> reliable` with an `accept` decision. The canonical scenario then verifies the chain, persists the reliability transition, verifies the outcome, and verifies the portable proof bundle.

## Failure catalog

1. A repeated webhook with the same event identity and bytes is accepted idempotently.
2. Reusing the same event identity with different bytes raises `IdentityConflictError`.
3. Evidence is deliberately tampered with after proof creation; chain verification rejects it.

## Expected output

The command prints JSON with `chain_verified`, `outcome_verified`, `proof_bundle_verified`, and `tamper_rejected` all set to `true`.

## Security notes

Only synthetic payment identifiers are used. No card number, secret, credential, or real gateway is contacted. Signature metadata is captured as evidence metadata; StateWake does not become the payment gateway.

## Limitations

The example demonstrates reliability evidence semantics, not payment authorization, settlement, fraud detection, or PCI compliance.

## Run and test

```bash
PYTHONPATH=src:. python docs/examples/golden/payment_reliability.py
pytest -q tests/integration/golden/test_golden_applications.py -p no:ddtrace -p no:anyio -p no:pytest_asyncio
```
