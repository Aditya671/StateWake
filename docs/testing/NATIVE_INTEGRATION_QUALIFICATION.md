# Native Integration Qualification

## Purpose

StateWake keeps **source regression** and **real native-SDK qualification** separate.
The frozen public-repository regressions prove that previously repaired StateWake
behavior remains intact. They do not, by themselves, prove compatibility with the
currently installed OpenAI Agents, LangChain, LangGraph, or LlamaIndex packages.

The existing coordinator is the authority for both layers:

```bash
python scripts/testing/run_public_trial_regressions.py --mode source
python scripts/testing/run_public_trial_regressions.py --mode qualification
```

Do not create a second qualification runner.

## Qualification boundary

The coordinator reads the integration extras directly from `pyproject.toml` and
records the installed distribution version for every SDK-backed case. Each case
contains two explicit test sets:

- `source_tests` — frozen regressions derived from the public-repository trial;
- `qualification_tests` — credential-free tests that instantiate and exercise
  the real installed SDK API.

A source-mode `PASS` is never promoted into native qualification.

## Required native probes

| Integration | Real SDK boundary exercised |
| --- | --- |
| OpenAI Agents | `TracingProcessor` plus real `trace()`, `generation_span()`, and `function_span()` lifecycle objects with StateWake installed as the only trace processor |
| LangChain | real `BaseCallbackHandler` plus an actual `BaseRetriever.invoke(...)` callback lifecycle |
| LangGraph | real `StateGraph` + `MemorySaver` checkpoint history read through `get_state_history(...)` |
| LlamaIndex | real `BaseEventHandler` type plus root dispatcher attachment and detachment |
| OpenTelemetry | real `SpanProcessor` registration plus completed GenAI span capture through a real `TracerProvider` |

The probes use local/in-memory objects only. They must not require API keys, paid
model calls, production data, or external side effects.

## Status semantics

Qualification mode is intentionally fail-closed:

- `PASS` — the declared integration distribution is installed and every required
  real-SDK probe executes without skips;
- `BLOCKED_ENV` — the declared integration distribution is not installed;
- `FAIL_INTEGRATION` — the SDK is installed but the native probe cannot collect,
  skips, or times out;
- `FAIL_STATEWAKE` — a source regression or native compatibility assertion fails.

A missing package, missing transitive module, skipped native test, timeout, or
collection error is never reported as a successful native qualification.

## Evidence output

Use explicit paths outside the release source tree:

```bash
python scripts/testing/run_public_trial_regressions.py \
  --mode qualification \
  --output /tmp/statewake-native-qualification.json \
  --report /tmp/statewake-native-qualification.md
```

The JSON record contains:

- exact Python executable and version;
- pinned upstream repository and commit for each frozen case;
- declared StateWake extra and requirement string;
- installed distribution version, or explicit missing state;
- source-regression subprocess evidence;
- native-qualification subprocess evidence;
- per-case and overall status.

The Markdown report is intentionally bounded: it shows case status and installed
SDK versions, but does not copy model prompts, retrieval content, tool payloads,
framework exceptions, or other untrusted producer data.

## Current package compatibility source

The supported package ranges remain the declarations in `pyproject.toml`:

```text
openai-agents>=0.3,<1
langchain-core>=0.3,<2
langgraph>=0.3,<2
llama-index-core>=0.12,<1
```

Do not hard-code a single third-party patch release into StateWake's runtime.
Qualification evidence records the exact version that was actually installed.

## Release and real-system relationship

Native qualification is a prerequisite for claiming that the advertised SDK
integration works in the tested environment. It still does **not** establish:

- successful paid/live model execution;
- correctness of the host application;
- factual truth of captured evidence;
- public-host end-to-end qualification;
- operator diagnostic gain;
- release publication authorization.

After native SDK qualification is green, use the same independent-oracle harness to
exercise credential-free real SDK host flows with durable StateWake capture:

```bash
PYTHONPATH=src:. python scripts/testing/system_trial.py qualify-native-hosts \
  --workspaces /tmp/statewake-native-hosts/workspaces \
  --evidence /tmp/statewake-native-hosts/evidence
```

This command calls the coordinator above as the native compatibility authority and
then runs separate host-owned truth exercises for all five SDK families. It writes
truth and StateWake event ledgers separately, reopens each native workspace
read-only to prove durable replay, scans generated evidence for synthetic secret
markers, and emits `native-host-qualification-summary.json` plus a bounded Markdown
report. A PASS still does not qualify external public repositories or paid/live
model execution.
