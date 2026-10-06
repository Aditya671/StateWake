# StateWake Real-System Validation Evidence Harness

## Purpose

The repository's deterministic comparative study is intentionally fixture-backed. It does not establish live-host effectiveness, operator diagnostic gain, or real operational overhead. `scripts/testing/system_trial.py` provides the missing **trial evidence harness** for those harder studies without turning StateWake into a generic test runner, evaluator, or chaos platform.

The harness is testing/research infrastructure. It is not part of the public `statewake` package API and it does not create a new reliability authority.

## Authority separation

The harness keeps four questions separate:

```text
host truth
    !=
StateWake capture
    !=
StateWake verification
    !=
operator interpretation
```

Host truth must come from a host-owned ledger or immutable synthetic fixture. StateWake output is never accepted as the oracle for StateWake.

## Workflow

From the repository root:

```bash
PYTHONPATH=src:. python scripts/testing/system_trial.py generate \
  --seed 4242 \
  --output /tmp/statewake-system-validation/datasets

PYTHONPATH=src:. python scripts/testing/system_trial.py validate-datasets \
  --input /tmp/statewake-system-validation/datasets

PYTHONPATH=src:. python scripts/testing/system_trial.py run \
  --input /tmp/statewake-system-validation/datasets \
  --workspaces /tmp/statewake-system-validation/workspaces \
  --evidence /tmp/statewake-system-validation/evidence \
  --offline

PYTHONPATH=src:. python scripts/testing/system_trial.py analyze \
  --input /tmp/statewake-system-validation/datasets \
  --evidence /tmp/statewake-system-validation/evidence \
  --reports /tmp/statewake-system-validation/reports
```

Generated evidence and reports belong **outside the release source tree**.

Validate the harness regression surface with:

```bash
PYTHONPATH=src:. python -m pytest tests/test_system_scenarios.py -q
```

## Golden no-new-code baseline

Every `run --offline` execution first runs the repository's three existing golden reference applications exactly through their documented source entry points:

- `examples/golden/payment_reliability.py`
- `examples/golden/enterprise_ai_reliability.py`
- `examples/golden/municipal_decision_reliability.py`

The harness writes only bounded execution metadata and stdout/stderr digests to `golden-baseline-results.jsonl`; it does not copy the golden JSON payload into trial evidence and does not use golden application output as independent host truth for later scenarios. A non-zero exit, timeout, malformed JSON response, or failed documented verification flag stops the campaign as `FAIL_INTEGRATION`.

## Local controls

`generate` creates three deterministic, credential-free local controls:

1. payment/webhook identity, duplicate delivery, and same-identity/different-bytes conflict;
2. stale RAG corpus identity where v1 was actually retrieved while v2 is current;
3. denied tool action where the independent policy/effect ledger records no side effect.

These controls exercise the harness and existing StateWake SDK boundaries. They are not substitutes for the public-repository trials or real native-SDK qualification.


## Native SDK host qualification

The harness also provides one credential-free native-host qualification path that
composes, rather than duplicates, the public-trial SDK coordinator:

```bash
PYTHONPATH=src:. python scripts/testing/system_trial.py qualify-native-hosts \
  --workspaces /tmp/statewake-native-hosts/workspaces \
  --evidence /tmp/statewake-native-hosts/evidence
```

The command first executes `run_public_trial_regressions.py --mode qualification`
through its shared programmatic authority. It then runs real local SDK host
exercises for OpenAI Agents, LangChain, LangGraph, LlamaIndex, and OpenTelemetry.
Each host maintains its own bounded truth ledger. StateWake capture is persisted to
a real workspace, the workspace is reopened read-only, and synthetic private-marker
leakage is checked before a framework can pass.

Generated evidence includes:

```text
native-sdk-qualification.json
native-host-truth-ledger.jsonl
native-host-event-ledger.jsonl
native-host-results.jsonl
native-host-qualification-summary.json
NATIVE_HOST_QUALIFICATION_REPORT.md
```

`external_public_hosts_qualified` remains `false`. This qualification proves the
installed SDK + local host boundary only; external public repositories still require
independently produced external-result envelopes or a separately authorized trial.

## External host results

A scenario can set `runner` to `external`. The harness then expects an operator-generated result envelope at:

```text
<evidence>/imports/<scenario_id>.<repeat>.json
```

If the envelope is absent, the run is `BLOCKED_ENV`, never `PASS`.

The external envelope contains separate `truth` and `observations` arrays. The harness does not infer unavailable fields and does not execute arbitrary commands from scenario data.

## Metrics

`analyze` derives only metrics supported by recorded observations:

- capture coverage;
- evidence completeness;
- fault recall and precision from effective injections and actual detector records;
- false-assurance count;
- reconstructability;
- paired operator diagnostic gain when `operator-assessments.jsonl` exists;
- wall-time percentiles from matched scenario measurements;
- synthetic privacy-marker leakage outside the restricted `privacy/` directory.

A missing measurement is reported as `NOT_MEASURED`; it is never silently replaced with a positive value.

## Reports

The analyzer creates:

```text
REAL_SYSTEM_VALIDATION_REPORT.md
COVERAGE_MATRIX.csv
DEFECT_REGISTER.md
REPRODUCIBILITY_REPORT.md
VALUE_ASSESSMENT.md
```

These are trial evidence. They do not authorize release publication or claim factual correctness of external systems.

## Boundaries

The harness intentionally does not:

- add commands to the public `statewake` CLI;
- run arbitrary shell commands supplied by dataset files;
- use StateWake reports as StateWake's ground truth;
- call paid/live services automatically;
- treat missing external SDKs or host results as success;
- convert a preserved reference into semantic truth;
- claim authorization merely because a tool call was captured;
- copy restricted/raw production payloads into generated reports.
