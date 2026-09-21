# StateWake v0.1.0 — Chaos, fuzz, and adversarial validation

**Validation date:** 2026-09-12

## Current campaign result

- **24 / 24** real-world scenarios passed.
- **8 / 8** deterministic chaos probes passed.
- **8 / 8** extreme probes passed, including 100,000 randomized lifecycle sequences.
- **8 / 8** deep failure-injection probes passed.
- **186** non-cryptographic regression tests passed in the current sandbox.
- Python compilation passed.
- `uv lock --check --offline` passed.

## Defects actually found and repaired

### 1. Low-level state predecessor integrity
JSONL and SQLite state persistence verified hash continuity but did not independently require `from_state` to equal the authoritative previous transition's `to_state`. The persistence boundary could therefore accept a cryptographically linked but semantically false predecessor. Both adapters now enforce the state-transition relationship.

### 2. Recovery boolean type confusion
A JSON value such as the string `"false"` could be coerced with `bool(...)` into `True`. Recovery approval now requires a JSON boolean.

### 3. Valid JSONL tail loss
A final valid record without a trailing newline was previously treated as an incomplete crash fragment and discarded. Recovery now parses the last record before deciding whether truncation is required.

### 4. Process-shared append semantics
The event and attestation JSONL stores lacked the same process-shared lock, complete-write loop, and `fsync` discipline used by the reliability-state store. Those writes now use the stronger persistence boundary.

### 5. Archive ambiguity / unexpected-member handling
Operational proof-bundle verification now rejects duplicate ZIP names and unexpected archive members before trusting their contents.

### 6. Silent malformed collection-member dropping
Several deserializers used comprehensions that filtered out malformed object members. This could turn a corrupt/hostile representation into a shorter apparently-valid object. The affected trust-anchor, lineage, comparison, and proof-source lists now reject malformed members.

### 7. SQLite indexed-column integrity gap
SQLite retained subject and digest as dedicated columns, but one read path trusted only the JSON payload. Direct tampering of the indexed columns could therefore go unnoticed. Reads now cross-check the indexed columns against the decoded transition.

### 8. Duplicate pytest configuration
A stale root `pytest.ini` overrode the canonical `pyproject.toml` configuration and removed the repository root from the test import path. The duplicate configuration was removed so `pyproject.toml` is authoritative.

### 9. Release-archive completeness
One release packaging pass omitted `.github/workflows`, causing the extracted release tree to fail repository governance tests. The final packaging rule now includes the repository governance/configuration tree while excluding transient caches/build output.

### 10. Numeric JSON type confusion
Security-sensitive integer fields now reject JSON booleans explicitly. This prevents values such as `true` from becoming integer `1` via Python's `int(...)` semantics.

## Attack classes exercised

- thread and multi-process concurrency;
- identical-event receipt storms;
- conflicting receipt storms;
- state-tip races;
- real process termination during writes;
- crash/partial-write retry;
- malformed and valid unterminated JSONL tails;
- event sequence duplication and cross-run confusion;
- SQLite payload/indexed-column corruption;
- provenance cycles and disconnected edges;
- randomized state-machine exploration;
- state-field type mutation and 10,000 random serialized mutations;
- duplicate ZIP members;
- archive path traversal;
- unexpected archive structures;
- evidence and portable-proof tampering;
- recovery transition abuse;
- HTTP verification boundary checks.

## Remaining architectural boundaries

A local append-only file cannot prove that a privileged storage attacker deleted an entire valid trailing segment unless an independent trusted checkpoint exists. Deployments needing deletion-detection require an external immutable or separately trusted anchor.

Unbounded attacker-controlled decompression is also a deployment resource-governance problem; file/request size limits and process/container resource controls remain necessary even when archive structure validation is correct.

## Reproducibility

```bash
python scripts/testing/run_real_world_scenarios.py
python scripts/testing/run_chaos_validation.py
python scripts/testing/run_extreme_validation.py
python scripts/testing/run_deep_chaos_validation.py
pytest -q
```

The current sandbox cannot execute the PyNaCl-dependent tests or the Ruff/mypy CLI because those dependencies are unavailable locally.
