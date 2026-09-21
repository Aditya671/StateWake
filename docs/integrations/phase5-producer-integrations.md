# Phase 5 Producer Integrations

StateWake Phase 5 adds thin producer integrations that convert external runtime signals into Phase 1 AI evidence contracts.

These integrations do **not** run AI workflows, judge model quality, configure external SDKs, publish releases, approve risk, or replace OpenTelemetry, CI/CD, LangChain, LlamaIndex, LangGraph, OpenAI Agents, or evaluator systems. They only normalize producer-side facts into digest-bound StateWake contracts.

## Implemented integration surfaces

| Module | Purpose | Required dependency |
|---|---|---|
| `statewake.integrations.opentelemetry_genai` | Maps OpenTelemetry GenAI-style spans/events into runtime, model, and tool contracts. | None beyond existing StateWake runtime dependency. |
| `statewake.integrations.openai_agents` | Maps OpenAI Agents trace/model/tool-like objects into runtime, model, and tool contracts. | None. The adapter reads mapping/object fields and does not import the SDK. |
| `statewake.integrations.langchain` | Maps LangChain callback-like model, tool, and retriever events into model, tool, and retrieval contracts. | None. |
| `statewake.integrations.llamaindex` | Maps LlamaIndex retrieval/evaluator-like events into retrieval and evaluator contracts. | None. |
| `statewake.integrations.langgraph` | Maps LangGraph run/checkpoint-like events into runtime trace contracts. | None. |
| `statewake.integrations.cicd` | Maps CI/CD release gate and test summary events into policy/evaluator contracts. | None. |
| `statewake.integrations.evaluators` | Maps framework-neutral evaluator results into evaluator contracts. | None. |

## Design rules

1. Core package imports must stay lightweight.
2. Optional framework SDKs must not be imported at `statewake` or `statewake.integrations` import time.
3. Adapters accept dictionaries or simple objects so tests can use deterministic fake events.
4. Raw prompt, request, response, tool input, and tool output bodies are not stored by default. Adapters digest normalized JSON payloads and preserve non-sensitive metadata.
5. Adapter output is a `ContractCaptureResult` containing the Phase 1 contract payload, derived `EvidenceItem`, and helper methods.
6. A capture result can be persisted into an explicit `StateWakeWorkspace` using `result.persist(workspace)`.
7. Built-in profile compatibility uses `profile_evidence_reference(result)` where Phase 1 contract names and Phase 2 profile-role names differ.

## Example

```python
from datetime import UTC, datetime

from statewake.integrations import capture_llamaindex_retrieval_event
from statewake.workspace import StateWakeWorkspace

workspace = StateWakeWorkspace.open("data/statewake")
try:
    result = capture_llamaindex_retrieval_event(
        {
            "run_id": "run-001",
            "corpus_identity": "knowledge-base-v1",
            "corpus_snapshot_id": "snapshot-2026-09-21",
            "query": {"text": "What changed?"},
            "retrieved_item_ids": ["doc-1"],
            "chunk_digests": ["0" * 64],
            "captured_at": datetime(2026, 9, 21, 0, 0, 0, tzinfo=UTC),
        }
    )
    record = result.persist(workspace)
finally:
    workspace.close()
```

## Dependency policy

No new hard runtime dependency is introduced by Phase 5. Exact optional framework versions must be selected only after real compatibility testing. Until then, SDK-specific adapters remain mapping/object-based producer boundaries.
