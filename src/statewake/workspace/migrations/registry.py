"""Migration ledger helpers for the SQLite workspace repository."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from .v0001_initial import MIGRATION_ID as V0001_INITIAL
from .v0002_ai_contracts import MIGRATION_ID as V0002_AI_CONTRACTS
from .v0003_claim_profile_results import MIGRATION_ID as V0003_CLAIM_PROFILE_RESULTS

MIGRATION_IDS = (
    V0001_INITIAL,
    V0002_AI_CONTRACTS,
    V0003_CLAIM_PROFILE_RESULTS,
)

_LEDGER_SQL = """
CREATE TABLE IF NOT EXISTS workspace_migrations (
    migration_id TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""


@dataclass(frozen=True, slots=True)
class MigrationRecord:
    """Represent one applied workspace migration marker."""

    migration_id: str
    applied_at: str


def ensure_migration_ledger(database: sqlite3.Connection) -> None:
    """Ensure the migration ledger exists and all compatibility markers are recorded."""
    database.execute(_LEDGER_SQL)
    applied = {
        str(row[0])
        for row in database.execute(
            "SELECT migration_id FROM workspace_migrations ORDER BY migration_id"
        ).fetchall()
    }
    now = datetime.now(UTC).isoformat()
    for migration_id in MIGRATION_IDS:
        if migration_id not in applied:
            database.execute(
                "INSERT INTO workspace_migrations (migration_id, applied_at) VALUES (?, ?)",
                (migration_id, now),
            )


def list_applied_migrations(
    database: sqlite3.Connection,
) -> tuple[MigrationRecord, ...]:
    """Return applied migration records in deterministic order."""
    if not _table_exists(database, "workspace_migrations"):
        return ()
    return tuple(
        MigrationRecord(migration_id=str(row[0]), applied_at=str(row[1]))
        for row in database.execute(
            "SELECT migration_id, applied_at FROM workspace_migrations ORDER BY migration_id"
        ).fetchall()
    )


def _table_exists(database: sqlite3.Connection, table_name: str) -> bool:
    row = database.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


__all__ = [
    "MIGRATION_IDS",
    "MigrationRecord",
    "ensure_migration_ledger",
    "list_applied_migrations",
]
