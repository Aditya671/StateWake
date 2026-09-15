> **Specification classification:** Active V1 specification.
>

# State Model v0.1

A `SystemState` captures the relevant inputs to an agent execution:

- agent version
- model
- prompt digest
- tool digests
- retrieval digest
- memory digest
- policy digest

The deterministic state fingerprint is the SHA-256 digest of these fields serialized as
canonical JSON (sorted keys, compact separators, UTF-8). `state_id` and `captured_at` are
metadata and are intentionally excluded from the fingerprint.
