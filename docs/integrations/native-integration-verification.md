# Native integration verification records

This file preserves time-specific native integration validation snapshots. Earlier `UNRUN-ENV` and candidate-status statements below describe those historical runs, not the current package status.

## Current workspace status (2026-09-26)

The package maturity classifier is `Development Status :: 5 - Production/Stable`. The current workspace passed these local gates:

| Gate | Result |
| --- | --- |
| `uv run mypy .` | PASS — 341 files checked |
| `uv run pytest -q` | PASS — 671 tests and 5 subtests |
| `uv run ruff check .` | PASS |
| `uv run ruff format --check .` | PASS |

These results supersede the earlier local-tool and SDK `UNRUN-ENV` entries below for the current workspace. Repository-host controls and publication approval remain separate release-process decisions.

## Historical snapshot: original attached archive

The first report below assessed an isolated copy of the attached StateWake v0.4.0 archive; it did not assess the current workspace.

## Implemented

- Optional native dependency extras: OpenAI Agents, LangChain Core, LangGraph,
  LlamaIndex Core, OpenTelemetry SDK, and an all-integrations extra.
- OpenAI Agents tracing processor with completed trace/span evidence, generation
  input/output digests, function tool input/output digests when observed.
- LangChain callback handler with model/tool/retrieval lifecycle correlation,
  content digests, explicit tool policy and explicit retrieval corpus identity.
- LangGraph real checkpoint-history reader with checkpoint parent identity and
  digests of serializable state values.
- LlamaIndex instrumentation listener with native event identity and retrieval
  node/query digests when sufficient context exists.
- OpenTelemetry SDK span processor tested with a real local SDK tracer.
- Explicit capture-failure accounting; no raw prompt, model output, tool input,
  retrieved content or checkpoint values in native runtime metadata.

## Recorded gate states

| Gate | State | Evidence |
| --- | --- | --- |
| Native integration unit tests, including real OpenTelemetry SDK span | PASS | `10 passed` |
| Unit/workspace/benchmark regression excluding PyNaCl-only attestation suite | PASS | `213 passed, 5 subtests passed` |
| Public API/repository/script/release-proof/benchmark selected tests | PASS | `24 passed` |
| Package build | PASS | `uv build --offline` built wheel and sdist |
| Wheel package boundary | PASS | `package boundary: verified statewake_ai-0.4.0-py3-none-any.whl` |
| Full pytest | UNRUN-ENV | PyNaCl missing during collection |
| Ruff and mypy | UNRUN-ENV | executables unavailable in this sandbox |
| Native OpenAI Agents, LangChain, LangGraph and LlamaIndex real SDK tests | UNRUN-ENV | respective SDKs not installed |
| Offline lock regeneration | UNRUN-ENV | missing baseline filelock cache and network disabled |
| Release supply-chain metadata contract | UPDATED | native SDKs are declared as optional extras; lock freshness remains a separate final-candidate gate |

Historical verification notes below describe earlier candidates and are retained as dated evidence rather than current installation guidance.

The original attached archive's manifest also contains **80 hash mismatches**
against its own eligible extracted files (475 entries, no missing/extra
entries). The original archive has not been altered. The working candidate's
manifest is regenerated from its own source, but that does not repair or
retroactively validate the original release manifest.

## Original snapshot outcome

That original snapshot had **not completed release verification**. Its dependency lock and SDK compatibility gates were unresolved at the time. The following notes retain the exact historical blockers; they do not describe the current workspace.

### Required local gates

```bash
uv lock
uv lock --check
uv sync --all-extras --group dev
uv run pytest -q
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy
uv build
PYTHONPATH=src:. python scripts/release/verify_package_boundary.py dist/statewake_ai-0.4.0-py3-none-any.whl
```

No Pyright gate is part of the v0.4.0 source configuration.

## Follow-up validation and evidence-integrity corrections

This section records a follow-up source snapshot made from the prior native
integration snapshot in a separate working directory. The original attached
v0.4.0 archive and the earlier snapshot were not modified.

### Confirmed fixes

- A completed native runtime observation now requires both its actual start and
  end timestamps. An absent timestamp is not silently replaced by the time of
  StateWake capture.
- OpenAI Agents native model and function evidence now hashes observed strings
  or canonical JSON structures, rather than Python object `str()`/`repr`.
  Opaque non-serializable values cause capture failure rather than a misleading
  process-specific digest.
- Added focused regressions under
  `tests/unit/integrations/test_native_evidence_boundaries.py`.

### Gates actually attempted in this follow-up

| Gate | State | Observed result |
| --- | --- | --- |
| Native-capture and evidence-boundary tests | PASS | `13 passed` |
| Unit/workspace/benchmark tests excluding PyNaCl attestation | PASS | `216 passed, 5 subtests passed` |
| Public API/repository/script/release-proof selection | PASS | `14 passed` |
| Full unfiltered pytest | UNRUN-ENV | PyNaCl is missing; collection stopped on trust-anchor and attestation tests |
| `uv lock --check --offline` | UNRUN-ENV | Cache lacks the required filelock dependency |
| `uv lock` | UNRUN-ENV | PyPI DNS lookup failed; no resolved lockfile was produced |
| Real native OpenAI Agents, LangChain, LangGraph and LlamaIndex tests | UNRUN-ENV | SDK distributions are unavailable in this environment |
| Ruff and mypy | UNRUN-ENV | Tools are unavailable in this environment |
| Offline package build and wheel boundary | PASS | `uv build --offline` built wheel + sdist; wheel package boundary verified |
| Supply-chain project metadata gate | FAIL | `6 failed, 2 passed`; new optional extras remain absent from `uv.lock` |

The new source improvements are **not** equivalent to completing SDK-version
compatibility or release verification. The prior gate blocker remains: refresh
`uv.lock` on an environment with registry access, then run the full repository
verification and real SDK smoke tests across the supported Python versions.
No Pyright gate is present or requested.

## Continued native evidence validation (2026-09-23)

This section applies to the isolated continuation of that **historical follow-up snapshot**.
The prior candidate and the original attached v0.4.0 artifact are not modified.

### Source correction

The LangChain native adapter previously used `str(messages)`, `str(response)`,
and `str(output)` as inputs to evidence digests. Those strings may include
process-dependent object representations rather than a canonical encoding of
what the SDK observed. The adapter now serializes JSON-compatible values or
SDK objects exposing `model_dump(mode="json")`, and rejects opaque/unserializable
values. Missing observations do not become valid evidence. Existing Phase 5
normalizers and contracts were preserved.

### Observed verification

- Native unit/workspace tests: **24 passed**.
- Unit/workspace/benchmark regression, excluding PyNaCl-dependent attestation: **218 passed, 5 subtests passed**.
- Selected public API/repository/release-proof tests: **14 passed**.
- `uv lock --check --offline`: **UNRUN-ENV** for resolution: pinned `filelock` package absent from the local resolver cache.
- `uv lock` (online): **UNRUN-ENV**: timed out amid repeated registry retries; no new lockfile was generated.
- Supply-chain metadata gate: **FAIL** because newly declared integration extras are not in `uv.lock`. This is not a release-verification pass.
- Real native SDK tests for OpenAI Agents, LangChain, LangGraph, and LlamaIndex: **UNRUN-ENV**: SDK distributions unavailable here.
- Full unfiltered pytest: **UNRUN-ENV**: PyNaCl is unavailable.
- Ruff and mypy: **UNRUN-ENV**: tools unavailable in this environment.

**Status recorded for the 2026-09-23 snapshot:** its lock refresh and full release gates were still pending. No Pyright gate was part of the v0.4.0 source configuration.
