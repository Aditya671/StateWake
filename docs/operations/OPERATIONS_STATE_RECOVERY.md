# State, Backup, Restore, and Recovery Operations

This document defines the reference operational contract for StateWake's durable reliability state. It does not introduce a hosted control plane or a scheduler.

## State ownership

A reliability-state history is authoritative for one state-store owner. A single logical writer must own a given history at a time.

### JSONL reference store

`JsonlReliabilityStateStore` is the dependency-light reference implementation.

- Store one subject history in a dedicated file or one explicitly shared history file.
- Writers must use the store's append operation; do not edit records in place.
- POSIX deployments use an advisory process lock. A process that dies releases the OS lock automatically.
- The fallback lock implementation uses a timestamped lock file and stale-lock age recovery when OS locking is unavailable.
- Readers verify the hash-linked transition history from the beginning of the file.

### Local repository initialization

The reference SQLite adapter creates its parent directory, database, and schema on first
use. A repository checkout can explicitly initialize the conventional local development
database with `python local validation databases created in temporary directories`, which creates
`data/statewake.db` when it is absent. The database itself is runtime state and is excluded
from source control.

### SQLite reference store

`SqliteReliabilityStateStore` is the reference transactional adapter for deployments that prefer SQLite.

- SQLite WAL mode is enabled for the database.
- `synchronous=FULL` is required for durable commits.
- State appends use `BEGIN IMMEDIATE` so the state transition check and insert are one transaction.
- The adapter is intentionally single-writer per database path; concurrent clients should serialize ownership through SQLite's transaction mechanism rather than opening independent application-level writers.

## Backup

Back up both the state database/history and the evidence artifacts referenced by the transitions. A state file without its referenced evidence is not sufficient to establish a trustworthy historical decision.

For JSONL, create a filesystem-level consistent snapshot while no append is occurring. For SQLite, use SQLite's online backup API or another SQLite-consistent backup mechanism; do not copy a live database by assuming ordinary file copying is always consistent with WAL state.

Backups must retain enough metadata to identify the source store, backup timestamp, and restore location.

## Restore procedure

1. Restore the state history/database and the referenced evidence artifact set into a controlled restore root.
2. Verify the restored state history from the first transition through the current tip.
3. Verify every evidence chain referenced by the restored transitions against the restored artifact root.
4. Verify any bound attestation, decision basis, comparison, reconciliation, and recovery artifacts.
5. Compare the restored current state with the last known authoritative state record.
6. Record the restore as an operational incident/recovery event and retain the evidence used to justify the restored state.

A restore is not considered trustworthy merely because the storage engine opened successfully. StateWake's evidence-chain and transition verification are the recovery proof.

## Incident recovery

When reliability state is restored after corruption, host loss, or storage migration, the recovery record should identify:

- the affected subject/store;
- source backup or recovery point;
- restored artifact set and evidence root;
- verification result and verifier version;
- operator/actor and timestamp;
- discrepancies found during recovery;
- the resulting reliability/reconciliation state and decision rationale.

The recovery record can then enter the normal external-evidence receipt/admission boundary and be bound into a subsequent reliability chain.

## Retention and legal hold

Retention requirements are represented through the `EvidenceRetentionRequirement` / `EvidenceRetentionAdapter` boundary. Implementations should keep reliability-state history, evidence artifacts, receipts, proof bundles, and recovery records for the same decision lineage together unless a documented retention policy explicitly separates them.

A legal hold must prevent deletion of held evidence even when ordinary retention expiry would otherwise permit cleanup. Hold identifiers and release events belong to the host's retention system; StateWake provides the adapter boundary rather than becoming the enterprise records system.

## Recovery invariant

The operational success condition is:

> A restored reliability decision can be independently re-verified from restored artifacts without trusting the crashed runtime, the operator's memory, or a live hosted control plane.
