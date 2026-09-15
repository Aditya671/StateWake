# First-party evidence adapters

StateWake provides thin receipt-producing adapters for evidence that already exists in
external systems. The adapters capture an artifact; they do not evaluate it,
interpret its producer semantics, run telemetry, schedule work, or become the
producer's runtime.

## Supported producer boundaries

| Adapter | Producer type | Expected input |
| --- | --- | --- |
| `CICDArtifactAdapter` | `ci-cd` | Existing build/test/release artifact |
| `OpenTelemetryTraceAdapter` | `opentelemetry` | Existing serialized trace export |
| `AgentRunLogAdapter` | `agent-run` | Existing agent/application run log |
| `EvaluationOutputAdapter` | `evaluation` | Existing evaluator output |
| `IncidentRecoveryRecordAdapter` | `incident-recovery` | Existing incident/recovery record |

The first-party file adapters use the same `EvidenceAdapterContext` plus the canonical local
content-addressed artifact and receipt stores. Their output is therefore an
`ExternalEvidenceReceipt` and enters the same admission/conformance boundary as
other external evidence.

## Example

The first-party adapters are available from the top-level `statewake` package. The
`for_root()` factory creates the reference local content/receipt stores without
requiring consumers to import internal storage modules.

```python
from pathlib import Path
from datetime import datetime, timezone
from statewake import CICDArtifactAdapter, EvidenceAdapterContext

adapter = CICDArtifactAdapter.for_root(
    EvidenceAdapterContext(
        producer_id="github-actions",
        source_event_id="build-42",
        run_id="release-42",
        metadata={"branch": "main"},
    ),
    root=Path(".statewake"),
)

receipt = adapter.ingest(
    Path("release-evidence.json"),
    captured_at=datetime.now(timezone.utc),
    source_ref="ci://release/42/release-evidence.json",
)
```

The returned receipt can then be admitted into the existing evidence-chain
lifecycle with `statewake.admit_evidence(...)`.

## Boundary guarantee

These adapters do not make claims about the correctness of the AI system or the
semantic truth of producer output. They establish producer/artifact identity,
content digest, capture metadata, and a durable receipt so downstream StateWake
verification can bind the artifact into a portable evidence chain.


## SDK producer-shape adapters

The framework-neutral SDK additionally provides webhook, queue/event, database-observation, batch/data-pipeline, and AI/agent adapters. These normalize producer metadata into the existing evidence-ingestion boundary; they do not replace the producer's execution or transaction authority.
