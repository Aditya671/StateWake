# Comparative Validation Study

Phase 7 adds a deterministic, fixture-backed study harness for comparing
StateWake against simpler baselines: final-output-only retention, conventional
logs, structured traces, and full StateWake evidence/profile/workspace/report
records.

The harness intentionally starts without live AI calls. This keeps regression
results reproducible and prevents the study from overstating conclusions beyond
its fixtures.

## Scope

The executable study covers five workloads:

1. RAG answer
2. Tool action
3. Incident recovery
4. Release verification
5. Human approval workflow

The fault catalog includes more than ten deterministic fault classes, including
omitted evidence, stale corpus identity, missing tool authorization, modified
output digest, erased recovery history, and unsigned release artifacts.

## Metrics

The first metrics are:

- verification coverage
- fault detection rate
- false-positive rate
- target/checkable property counts

Human reconstruction time, runtime overhead, storage overhead, and live-model
behavior require a separate measured study and are not claimed by this fixture
harness.

## Usage

```python
from statewake.validation_study import run_comparative_validation_study

study = run_comparative_validation_study()
print(study.digest)
```

Reports can be rendered through:

```python
from statewake.validation_study.report import render_study_json, render_study_markdown
```

## Boundaries

The study report must state its limitations. It does not claim general
statistical superiority beyond the tested workloads and injected faults.
