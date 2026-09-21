# StateWake Golden Reference Applications

These three applications are the polished validated reference implementations. Each uses a synthetic producer, the public StateWake integration SDK, and the existing canonical reliability lifecycle.

They are intentionally credential-free and do not represent real payment, enterprise, or municipal policies.

## Applications

| Application | Producer shape | StateWake boundary | Deliberate failure |
|---|---|---|---|
| Payment Reliability | payment gateway + webhook | `WebhookEvidenceAdapter` | duplicate delivery is idempotent; same event ID with different bytes is rejected |
| Enterprise AI Reliability | agent / RAG workflow | `AgentEvidenceAdapter` | stale retrieval is represented as a behavioral-evidence reliability change |
| Municipal Decision Reliability | service request + rules decision | `StateWakeClient.ingest_bytes` | policy-version change produces a degraded/review outcome |

## Run

From the repository root:

```bash
PYTHONPATH=src:. python docs/examples/golden/payment_reliability.py
PYTHONPATH=src:. python docs/examples/golden/enterprise_ai_reliability.py
PYTHONPATH=src:. python docs/examples/golden/municipal_decision_reliability.py
```

Each command prints JSON showing evidence receipt identity, chain verification, outcome verification, proof-bundle verification, tamper rejection, and the deliberate failure demonstrated by the application.

## Architecture

```text
synthetic producer
      |
      v
StateWake Integration SDK
      |
      v
canonical evidence admission
      |
      v
reliability evidence chain
      |
      v
state transition + attestation
      |
      v
portable proof verification
```

The producer remains authoritative for its own business operation. StateWake records and verifies the evidence supporting the reliability claim; it does not become the producer's runtime, gateway, RAG engine, or municipal policy engine.

## Limitations

- All business data is synthetic.
- The examples do not call external services.
- The enterprise AI example uses references rather than sensitive prompts, retrieved documents, or model payloads.
- Municipal outcomes are demonstrations of evidence-backed review semantics, not actual public policy.
