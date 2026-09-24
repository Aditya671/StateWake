# Native SDK import and hook audit — 2026-09-23

**Source candidate:** `statewake_native_sdk_integrations_v040_continued_candidate.zip`, extracted read-only into the baseline folder and edited only in a separate working directory. **Status:** development candidate; no release approval.

## Confirmed upstream interfaces and source decisions

| Native surface | Official upstream interface | Source correction / assessment |
| --- | --- | --- |
| OpenAI Agents | `agents.tracing.processor_interface.TracingProcessor`, callbacks `on_trace_start`, `on_trace_end`, `on_span_start`, `on_span_end`, `shutdown`, `force_flush` | Import from the defining module, not an assumed namespace re-export. Processor methods retained. |
| LangChain | `langchain_core.callbacks.base.BaseCallbackHandler`, `on_chat_model_start(serialized, messages, ...)`, `on_llm_end`, tool/retriever callbacks | Import from the defining module rather than relying on `langchain_core.callbacks` re-export. Existing signatures retained. |
| LlamaIndex | `llama_index.core.instrumentation.event_handlers.BaseEventHandler`, `handle(event)`, `class_name()`, `get_dispatcher(name).add_event_handler(handler)` | Added explicit `class_name()` override. A missing source event timestamp is now a capture failure, not an invented observation time. |
| LangGraph | `graph.get_state_history(config, limit=...)` and `StateSnapshot` (`config`, `parent_config`, `created_at`, `values`, `tasks`, `interrupts`) | No LangGraph class import needed by existing duck-typed history reader. Added real-SDK smoke gate. |
| OpenTelemetry | `opentelemetry.sdk.trace.SpanProcessor`, `on_start`, `on_end`, `shutdown`, `force_flush` | Existing import is valid in the installed SDK. Added explicit runtime import/instance test. |

Official reference pages inspected:

- https://openai.github.io/openai-agents-python/ref/tracing/processor_interface/
- https://reference.langchain.com/python/langchain-core/callbacks/base/BaseCallbackHandler
- https://reference.langchain.com/python/langchain-core/callbacks/base/CallbackManagerMixin/on_chat_model_start
- https://github.com/run-llama/llama_index/blob/main/llama-index-core/llama_index/core/base/base_retriever.py
- https://github.com/run-llama/llama_index/blob/main/llama-index-instrumentation/src/llama_index_instrumentation/dispatcher.py
- https://reference.langchain.com/python/langgraph/types/StateSnapshot

## Error-reporting correction

Native construction errors now explain that the corresponding extra is needed only when the SDK's own namespace is absent. A missing transitive dependency is no longer silently relabeled as a missing StateWake integration extra; the underlying import failure propagates so it can be corrected at the proper package/version boundary.

## Executable smoke gates

`tests/unit/integrations/test_native_sdk_import_contracts.py` imports each real native base and constructs a corresponding StateWake integration. The LangGraph case also executes a local in-memory checkpointed graph without a paid model or network call. Tests are skipped when the optional SDK is absent; a present SDK with an invalid import, incompatible abstract class, or broken checkpoint API produces **FAIL**, not **PASS**.

The earlier fake SDK tests were updated to mock the defining package paths rather than incorrect re-exports. Fake imports and events prove local adapter logic, **not** compatibility with installed real SDKs.

## Limits and release blocker

- Real OpenAI Agents, LangChain, LangGraph, and LlamaIndex SDKs are absent in this environment; their smoke tests cannot establish installed-SDK compatibility here.
- OpenTelemetry SDK is present, including the real span lifecycle regression.
- The optional integration extras remain unresolved in `uv.lock`. No lock entries were invented; supply-chain verification must stay blocked until actual dependency resolution and a full release gate pass on the same candidate.
- No Pyright gate was introduced; use the repository's mypy gate.
