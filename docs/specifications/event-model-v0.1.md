> **Specification classification:** Historical reference.
>

# Event Model v0.1

The planned event envelope will contain:

```text
run_id
sequence
occurred_at
event_type
actor
name
state_id
payload_ref
metadata
```

Event payloads should be stored separately when they contain large or sensitive content. A reference/digest is preferred in the immutable event envelope.

## Implemented v0.0.1 capture shape

The envelope is implemented as `EventEnvelope` and currently contains:

- `run_id` — execution identifier
- `sequence` — zero-based contiguous event position within the run
- `occurred_at` — timezone-aware event timestamp
- `event_type` — stable event category
- `actor` — component responsible for the event
- `name` — optional human-readable operation name
- `state_id` — optional system-state reference
- `payload_ref` — optional external payload reference
- `metadata` — small string key/value metadata only

The local JSONL adapter writes one canonical JSON object per line and never rewrites existing records during append. Large or sensitive payloads remain outside the envelope and should be referenced by `payload_ref`.

## State and evidence boundary in v0.0.2

A run may reference a `SystemState` by `state_id`. The state snapshot fingerprints the
behaviorally relevant configuration using canonical JSON and SHA-256; capture time and
the human-selected identifier do not affect the fingerprint. Evidence is represented by
an `EvidenceManifest` containing immutable references to supporting material.
