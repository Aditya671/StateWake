# StateWake Workspace Production Operations

This runbook describes the operational boundary of a `StateWakeWorkspace` after
Tier 15. It does not replace the existing StateWake security, evidence, or
reliability authorities.

## Where data lives

An embedded workspace keeps its operational SQLite index at `statewake.sqlite3`.
Canonical evidence payloads live under `artifacts/`, canonical evidence receipts
under `receipts/`, workspace-controlled exports under `exports/`, the manifest
under `manifests/`, and transient mutation locks under `locks/`.

The SQLite repository and StateWake evidence stores remain authoritative for their
respective data. Exports are derived data; they are tracked in the operational
index but are not the source of truth for canonical evidence.

## Health and diagnostics

Use `workspace.verify()` for the full integrity report. Use
`workspace.diagnostics()` when an engineer also needs storage usage, backend
identity, and the most recent export metadata.

A healthy verification report means the verification contract found no integrity
errors. A report with limitations, incomplete data, invalid metadata, or corruption
must be interpreted using its issue codes rather than treated as a generic failure.

## Concurrency

Workspace mutations use a filesystem lock at `locks/workspace.operations.lock`.
Read-only queries and analytical access do not require this mutation lock.
Long-running maintenance should acquire the same lock for the entire mutation
window so that ingestion, exports, retention, and deletion do not overlap.

## Backup and restore

For an embedded workspace, take a filesystem-level backup of the complete workspace
root while mutation operations are quiesced. Include the SQLite database, WAL/SHM
state when present, artifacts, receipts, exports, manifests, and lifecycle metadata.
Do not back up only the SQLite database because canonical evidence payloads and
receipts are separate stores.

Restore by replacing the workspace root from a known-good backup, reopen the
workspace, and run `workspace.verify()`. A successful reopen alone is not a
substitute for integrity verification.

For an externally managed or enterprise repository, back up the repository using
its own transactional backup mechanism and preserve the same evidence-store and
workspace-manifest relationship. The stable repository protocol is the integration
boundary; the portable bundle is the supported data portability boundary.

## Export history

`workspace.export_history()` returns persisted metadata for completed workspace
exports in deterministic order. Export files remain derived data and should be
recreated from canonical workspace records when appropriate.

## Retention and recovery

Retention policies and legal holds are durable workspace state. Expired payloads
are deleted through the existing canonical artifact adapter and retain payload-free
deletion history. After an interrupted maintenance operation, reopen the workspace,
run verification, inspect lifecycle/deletion state, and retry only operations whose
preconditions are still satisfied.

## Embedded and enterprise deployment guidance

Embedded deployments can use the default SQLite repository directly on a durable
local workspace filesystem. Deployments that provide another implementation of the
stable `StateWakeRepository` contract can substitute that backend without changing
workspace query semantics, evidence authority, export semantics, or lifecycle rules.

Operational tooling should treat `verify()`, `diagnostics()`, `export_history()`,
and the existing lifecycle APIs as the explanation surface rather than reading raw
SQLite or evidence files directly.
