# StateWake Integration SDK

## Purpose

The integration SDK reduces producer-side adoption cost while preserving the
existing StateWake reliability authorities. It is a thin boundary: it captures
producer evidence and delegates persistence to the canonical evidence-ingestion
adapter.

## Stable Python surface

```python
from statewake import IntegrationContext, StateWakeClient

client = StateWakeClient.for_root(
    IntegrationContext(producer_id="orders-service", run_id="run-123")
)
receipt = client.ingest_bytes(
    b"event payload",
    producer_type="application",
    source_ref="event-123",
    source_event_id="event-123",
)
client.verify_receipt(receipt)
```

Applications do not need to import StateWake services or construct content and
receipt stores themselves.

## Adapter families

The SDK currently provides independent, framework-neutral adapters for the
following producer shapes:

| Adapter | Evidence boundary |
| --- | --- |
| `WebhookEvidenceAdapter` | HTTP request body plus request/delivery metadata |
| `QueueEvidenceAdapter` | Message bytes plus message/delivery metadata |
| `DatabaseEvidenceAdapter` | Transaction and entity observation |
| `BatchEvidenceAdapter` | Pipeline run and input/output references |
| `AgentEvidenceAdapter` | Model and execution references for AI/agent runs |

These adapters deliberately do not become webhook servers, queue consumers,
database transaction managers, batch orchestrators, or agent runtimes.

## Identity and idempotency

StateWake keeps producer identity, run identity, source-event identity, artifact
identity, and receipt identity distinct. Adapters use a source-event identity
when one is available. Repeating the same event and content is idempotent at
the canonical receipt boundary; reusing an event identity with different content
is rejected as an identity conflict.

## Sensitive data

The SDK prefers references and digests for structured AI/agent evidence. It does
not require prompt, tool-result, payment, or other sensitive payloads to be
stored inside the structured record. Payload storage remains an explicit caller
decision and is subject to the host application's privacy policy.

## Error boundary

The SDK exposes `StateWakeIntegrationError` as the integration exception base,
with `InvalidEvidenceError`, `IdentityConflictError`, and `PersistenceFailureError` for common
machine-classifiable failures. The canonical reliability services remain the
authority for state transitions, evidence-chain verification, attestation, and
proof verification.

## Architecture rule

```text
Producer
   |
   v
StateWake SDK adapter
   |
   v
Canonical evidence ingestion
   |
   +--> content-addressed artifact
   +--> immutable receipt
   |
   v
Reliability evidence lifecycle
```

No second evidence authority is introduced by the SDK.
