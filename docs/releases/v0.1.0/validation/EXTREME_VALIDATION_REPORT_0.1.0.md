# StateWake v0.1.0 — Extreme Failure-Injection Validation

## Scope

This campaign attempts to break StateWake at the reliability boundary rather than only exercising happy-path examples. It covers:

- multi-thread and multi-process concurrency;
- partial writes and crash-retry behavior;
- append-only JSONL corruption;
- SQLite corruption;
- provenance cycles;
- randomized state-machine exploration;
- hostile operational ZIPs;
- path traversal and unexpected archive members;
- evidence receipt identity conflicts;
- evidence and proof tampering;
- the HTTP verification boundary;
- 18 representative global application domains.

## Results

| Layer | Result |
|---|---:|
| Global real-world scenarios | **18 / 18 passed** |
| Extreme failure-injection probes | **8 / 8 passed** |
| Regression tests in available environment | **181 passed** |
| Python compilation | **passed** |
| Deliberate evidence tampering | **rejected** |
| Invalid reliability transitions | **rejected** |
| Concurrent content writes | **passed** |
| Concurrent receipt identity conflicts | **passed** |
| Concurrent state-tip races | **passed** |
| Multi-process event-log writes | **passed** |
| Multi-process attestation races | **passed** |
| SQLite payload corruption | **rejected** |
| ZIP duplicate/extra-member attacks | **rejected** |
| Provenance cycle fuzzing | **rejected** |

## Defects found during this campaign

### JSONL complete-tail data loss

The reliability-state JSONL adapter treated any final record without a trailing newline as a partial crash tail and deleted it. A complete, valid JSON record could therefore disappear merely because a producer wrote it without a final newline.

The recovery path now first parses and validates the final non-newline-terminated record. A valid record is preserved; only an actually malformed final record is truncated.

### Persistence concurrency mismatch

The general event JSONL store and reliability-outcome attestation store did not provide the same process-shared locking and durable append semantics already used by the reliability-state store.

Both now use process-shared file locks, complete `os.write` loops, and `fsync` before an append returns.

### Portable ZIP member ambiguity

The bundle verifier previously read every ZIP member before comparing the archive contents with the manifest. An attacker could therefore force decompression of unexpected members before the bundle was rejected.

The verifier now rejects duplicate ZIP names and rejects unexpected/missing members before reading artifact payloads. It also compares archive member sizes with manifest sizes before reading them.

### Test-suite contract drift

The repository test configuration did not expose the `scripts` package during a clean `pytest -q` run, causing integration-test collection failures. The test path now includes the repository root.

When the global scenario matrix expanded from six to eighteen scenarios, a stale assertion still expected six. That assertion was updated to validate the new explicit matrix size.

## Fail-closed checks

The campaign deliberately attempts to:

1. use malformed state predecessors;
2. create cyclic provenance;
3. mutate evidence after receipt creation;
4. mutate proof-bundle contents;
5. introduce duplicate receipt identities with conflicting bytes;
6. append malformed JSON tails;
7. corrupt persisted SQLite payloads;
8. smuggle unexpected ZIP members;
9. use invalid path components;
10. cross an invalid state-machine transition.

All these conditions were rejected by the hardened implementation.

## Known architectural limits

A local append-only file cannot, by itself, prove that a privileged filesystem attacker did not delete an entire valid trailing history segment. Hash chaining detects modification of records that remain in the file; it cannot cryptographically anchor the existence of records that have been deleted unless an independent trusted tip/checkpoint exists.

That is an architectural boundary, not something a local JSONL lock can solve. Deployments that require deletion/rollback detection against privileged storage administrators need an external trust anchor such as an immutable object store, remote append-only log, signed checkpoint service, or equivalent independent retention control.

Similarly, local bundle verification cannot make arbitrarily large attacker-controlled decompression safe without a deployment-level resource budget. The verification adapter should therefore be deployed behind explicit file/request size limits and operating-system resource controls appropriate to the workload.

## Reproducible commands

```bash
python scripts/testing/run_real_world_scenarios.py
python scripts/testing/run_chaos_validation.py
python scripts/testing/run_extreme_validation.py
pytest -q
```

The local sandbox used for this report does not contain the project's PyNaCl/Ruff/mypy executables, so the cryptographic test module and those exact static-analysis commands are not represented as locally executed results here. The project owner has independently confirmed those tools work in the development environment; the remaining authoritative gate is the actual local/CI execution against the exact release tree.
