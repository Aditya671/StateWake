# AI Evidence Contracts

StateWake AI evidence contracts capture the material producer facts needed to verify an AI-system outcome later. They do not judge model quality, optimize prompts, sandbox tools, or replace external telemetry/evaluation systems.

The first contract family is implemented under `statewake.ai_contracts` and covers:

- prompt construction evidence;
- model invocation evidence;
- tool-call evidence;
- retrieval evidence;
- policy decision evidence;
- evaluator evidence;
- human approval evidence;
- runtime trace, retry, and recovery evidence.

Each contract carries a schema version, contract version, producer identity, run identity, digest-bound material data, and timezone-aware UTC capture time. Contract payloads serialize with sorted JSON keys and compact separators so their digests remain deterministic.

Every contract can be converted into the existing `EvidenceItem` model. Workspace persistence stays explicit: callers ingest the serialized contract bytes through `StateWakeWorkspace.ingest(...)` and provide the workspace root themselves.
