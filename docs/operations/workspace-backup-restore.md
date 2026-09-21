# Workspace Backup, Restore, and Migration Guarantees

## Purpose

Phase 4 makes the local StateWake workspace durable across restart, backup, restore, export, and payload-integrity scenarios without replacing the existing SQLite workspace repository or portable dataset bundle surfaces.

StateWake still treats the content-addressed artifact store as authoritative for payload bytes and the SQLite database as the operational index. Backup and restore preserve both layers together.

## Workspace location

The default workspace root is now durable:

```text
data/statewake/
└── statewake.db
```

Tests that need isolation should still pass an explicit temporary workspace path, for example `StateWakeWorkspace.open(tmp_path / "statewake")`.

## Schema and migration boundary

The current physical SQLite schema remains `PRAGMA user_version = 1` and the workspace manifest records `schema_version = "1"`.

Phase 4 adds explicit migration markers under `statewake.workspace.migrations`:

```text
v0001_initial
v0002_ai_contracts
v0003_claim_profile_results
```

The Phase 1 AI contracts and Phase 2 claim-profile results are persisted through the existing evidence-receipt boundary, so no duplicate physical table was introduced for those payloads. Future physical migrations should add a new module, update the registry, and add a compatibility fixture before changing the repository schema.

## Backup

Use the workspace method:

```python
backup = workspace.backup(Path("backup.zip"))
```

A backup is created only after workspace verification succeeds. The backup ZIP includes a backup manifest, checksums, the SQLite index, manifest, receipts, artifacts, exports, and other durable workspace files. Lock files and temporary files are not included.

## Restore

Use the class method:

```python
StateWakeWorkspace.restore_backup(Path("backup.zip"), Path("restored-statewake"))
```

Restore verifies:

- backup format and schema markers;
- declared member set;
- member SHA-256 checksums;
- safe relative paths;
- content-addressed artifact payload digests;
- workspace reopen and verification after extraction.

## Integrity sweep

Use:

```python
workspace.integrity_sweep()
```

The sweep verifies that every artifact path under `artifacts/` still matches its SHA-256 content address. A modified payload fails the sweep instead of being silently accepted.

## Non-goals

Phase 4 does not add a second database format, merge portable dataset bundles with workspace backups, or make StateWake a cloud backup service. It keeps backup and restore local, deterministic, and evidence-oriented.
