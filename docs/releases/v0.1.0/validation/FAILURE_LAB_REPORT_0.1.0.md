# StateWake Failure Laboratory

## Purpose

The failure laboratory is a deterministic, credential-free adversarial validation boundary. It does not replace the StateWake reliability core, become a generic chaos platform, or mutate production data. Each case creates isolated temporary state and verifies a specific fail-closed invariant.

## Historical audit disposition

The canonical baseline already contained three useful but overlapping validation streams:

- `scripts/testing/run_chaos_validation.py` — deterministic concurrency, provenance, predecessor, and ingestion probes.
- `scripts/testing/run_extreme_validation.py` — process races, crash/retry, persistence corruption, event tails, provenance fuzzing, randomized state transitions, and archive attacks.
- `scripts/testing/run_deep_chaos_validation.py` — 10K state mutations, multi-process receipt conflicts, process-crash tails, SQLite corruption variants, event tampering, and archive structure variants.

These implementations were retained as historical/compatibility validation evidence. They were not duplicated into a second reliability authority.

The missing capability was a **single attack catalog and executable failure-lab interface** covering the roadmap's mutation, race, crash, archive, storage, HTTP, and cryptographic boundaries with one deterministic result schema.

## Canonical attack catalog

| ID | Category | Boundary |
| --- | --- | --- |
| `state-mutation` | mutation | serialized reliability state |
| `race-engine` | race | concurrent content/state writes |
| `crash-harness` | crash | real process partial JSONL write |
| `archive-attack` | archive | duplicate/traversal/absolute ZIP members |
| `storage-corruption` | storage | SQLite persisted-field corruption |
| `http-mutation` | HTTP | oversized and malformed requests |
| `crypto-mutation` | crypto | message/signature mutation |
| `event-mutation` | mutation | duplicate event sequence |
| `provenance-mutation` | mutation | cyclic provenance |
| `receipt-identity-race` | race | concurrent producer occurrence ingestion |

The campaign uses seed `20260913` for deterministic mutation generation.

## Result contract

`python scripts/testing/failure_lab.py --ci` emits JSON with:

- `schema_version`
- `seed`
- `passed`
- `attack_count`
- `results[]`

Each result identifies the attack, category, description, pass/fail status, and—on failure—the exception type and message.

## Regression rule

Every discovered defect from the failure laboratory must become deterministic regression coverage before the capability is promoted. The laboratory itself is also a regression test through `tests/test_failure_lab.py`.

## Execution

```bash
python scripts/testing/failure_lab.py --ci
pytest -q
```

The cryptographic case requires the declared PyNaCl dependency. The isolated validation sandbox may use the same temporary compatibility harness used by the canonical regression process when native PyNaCl is unavailable.
