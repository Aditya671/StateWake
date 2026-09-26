# Native framework capabilities — v0.4.0 development extension

This document applies to the **isolated development copy** of StateWake v0.4.0.
It does not change the uploaded verified release, which remains the baseline.

## Installation

`pyproject.toml` now declares separately installable native integration extras:

```bash
uv sync --extra integrations-openai-agents
uv sync --extra integrations-langchain
uv sync --extra integrations-langgraph
uv sync --extra integrations-llamaindex
uv sync --extra integrations-opentelemetry
# Or request all five frameworks:
uv sync --extra integrations
```

Core Phase 1 contracts and existing Phase 5 event-mapping functions remain in place; native SDK modules are imported only when a native handler is constructed. The base package therefore remains usable when no framework extra is installed. Missing SDKs produce an integration-specific install instruction rather than failing `import statewake`.

The `integrations` extra is convenience metadata for installing all five supported native SDK families in one compatible environment. It does not claim that every historical framework version can coexist; each advertised version range must still pass its SDK-backed compatibility tests.

## Native observation entry points

| Framework | Native hook | Produced evidence |
|---|---|---|
| OpenAI Agents | `create_agents_trace_processor(sink)`; register with `agents.add_trace_processor(processor)` | Completed trace/span runtime evidence; observed generation and function tool digests where available. |
| LangChain | `create_langchain_callback_handler(sink, ...)`; pass to runnable's `callbacks` | Paired model/tool/retrieval runtime events; model/tool/retrieval contracts when all required observed inputs and configured policy/corpus identities exist. |
| LangGraph | `capture_langgraph_history(graph, config, sink)` | Native checkpoint ID, parent checkpoint link, state digest, task/interrupt counts; requires actual checkpointer and `thread_id`. |
| LlamaIndex | `attach_llamaindex_event_handler(sink, dispatcher_name=...)` | Native event identity/class/timestamp and retrieval query/node digests when corpus identity, snapshot and citation boundary are provided. |
| OpenTelemetry SDK | `provider.add_span_processor(create_genai_span_processor(sink))` | Completed span identity, actual start/end, error status, bounded GenAI identifiers. |

The sink supports `snapshot()` and `failures`. Native retrieval/generation/tool evidence is emitted only when the corresponding observation contains sufficient real data; no empty placeholder digest is treated as evidence. Each captured result supports
`result.persist(workspace)` for explicit durability. Capture failures must be
inspected; an absent contract does not prove a successful or authorized event.

## Example: real OpenTelemetry SDK

```python
from opentelemetry.sdk.trace import TracerProvider
from statewake.integrations import NativeCaptureSink, create_genai_span_processor

sink = NativeCaptureSink()
provider = TracerProvider()
provider.add_span_processor(create_genai_span_processor(sink))
tracer = provider.get_tracer("application")
with tracer.start_as_current_span("agent.step") as span:
    span.set_attribute("statewake.run_id", "run-001")
    span.set_attribute("gen_ai.operation.name", "chat")
# A runtime contract now exists; raw prompt/output attributes were not copied.
assert sink.snapshot()
assert not sink.failures
```

## Boundaries and known limitations

- These integrations **observe the SDKs**; they do not replace their execution,
  checkpointing, retriever or tracing backends. Native SDK use is a deliberate
  capability, not a framework-neutral substitute.
- Observing a successful tool span does **not** prove authorization. Explicit
  classification and authorization must be supplied for authorization-bearing
  contracts. Missing policy evidence is a recorded capture failure.
- LangChain corpus identity, snapshot identity, and citation boundary must be
  supplied by the host application; native retriever callbacks alone do not
  establish a durable corpus snapshot.
- Raw prompts, model outputs, tool inputs/outputs, and checkpoint values are
  not stored in the native runtime metadata. Where supported, values are
  digested; callback failures record only stage and exception class.
- Registering an OpenAI trace processor does **not** disable the SDK's other
  exporters. Applications must configure tracing/export/redaction separately;
  setting a StateWake processor alone is not a privacy guarantee.
- OpenAI Agents, LangChain, LangGraph and LlamaIndex **real SDK execution tests**
  remain `UNRUN-ENV` here because those packages are absent. Fake native
  callback protocol tests exercise the implemented StateWake behavior but do
  not establish compatibility with all SDK releases.
- No `pyright` gate is added; StateWake v0.4.0 uses **mypy**.
