# StateWake Golden Reference Applications Verification

## Audit decision

Historical StateWake archives were audited before implementation. No historical archive contained three complete, executable golden applications satisfying the reference-application contract. Existing `docs/examples/first-evidence-chain.py` and the 24-scenario runner are valuable validated references, but neither provides the required three polished producer applications using the StateWake integration SDK.

Therefore this stage extends the existing validated example/scenario frontier rather than duplicating or replacing the reliability core.

## Implemented applications

1. **Payment Reliability** — synthetic payment producer using `WebhookEvidenceAdapter`; demonstrates idempotent duplicate delivery, producer-identity conflict rejection, complete proof verification, and evidence tamper rejection.
2. **Enterprise AI Reliability** — synthetic agent/RAG producer using `AgentEvidenceAdapter`; records model/prompt/retrieval/tool/output/evaluator references without sensitive payloads and executes the existing evidence lifecycle.
3. **Municipal / Decision Reliability** — synthetic service producer using `StateWakeClient.ingest_bytes`; models a policy-version change as `degraded` / `review` rather than silently accepting an unverified change.

## Shared lifecycle

```text
producer
  -> integration SDK
  -> canonical evidence admission
  -> evidence chain verification
  -> reliability state transition
  -> outcome attestation
  -> portable proof verification
  -> deliberate tamper/failure verification
```

## Verification evidence

The three applications execute successfully and the dedicated regression tests require:

- evidence receipt creation;
- evidence-chain verification;
- outcome verification;
- portable proof-bundle verification;
- deliberate failure visibility;
- deliberate evidence-tamper rejection.

The complete suite after this stage contains **221 tests**.

## Boundary preservation

The applications do not turn StateWake into a payment gateway, LLM/agent runtime, municipal rules engine, queue, workflow engine, or observability platform. Producer systems remain authoritative for their own operations.

All application data is synthetic and credential-free.
