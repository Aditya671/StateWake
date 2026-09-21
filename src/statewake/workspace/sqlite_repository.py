"""SQLite implementation of the StateWake workspace repository."""

from __future__ import annotations

import sqlite3
from datetime import UTC
from pathlib import Path

from ..domain.data_lifecycle import DeletionRecord
from ..domain.governance import SENSITIVITY_ORDER
from ..utils.time import parse_datetime
from .errors import (
    CorruptWorkspaceDatabaseError,
    UnsupportedWorkspaceSchemaError,
    WorkspaceRecordConflictError,
)
from .models import (
    WorkspaceExport,
    WorkspaceIdentity,
    WorkspaceRecord,
    WorkspaceRecordIndexEntry,
    WorkspaceRecordQuery,
    WorkspaceRetention,
)
from .repository import (
    StateWakeRepository,
    WorkspaceIntegritySnapshot,
    WorkspaceTransaction,
)
from .schema import EXPECTED_INDEXES, EXPECTED_TABLES, SCHEMA_SQL, SCHEMA_VERSION


class SqliteWorkspaceRepository(StateWakeRepository):
    """Persist the workspace operational index in a local SQLite database."""

    def __init__(self, path: Path) -> None:
        """Initialize a repository bound to the supplied database path."""
        self.path = path

    def initialize(self) -> None:
        """Create the versioned schema or validate an existing schema."""
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._validate_file_header()
            with self.connect() as database:
                version = int(database.execute("PRAGMA user_version").fetchone()[0])
                if version > SCHEMA_VERSION:
                    raise UnsupportedWorkspaceSchemaError(
                        f"workspace database schema {version} is newer than "
                        f"supported schema {SCHEMA_VERSION}"
                    )
                tables = self._table_names(database)
                indexes = self._index_names(database)
                if version == 0:
                    if tables:
                        raise CorruptWorkspaceDatabaseError(
                            "workspace database has unversioned tables"
                        )
                    with database:
                        database.executescript(SCHEMA_SQL)
                        database.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
                    return
                if (
                    version != SCHEMA_VERSION
                    or tables != EXPECTED_TABLES
                    or indexes != EXPECTED_INDEXES
                ):
                    raise UnsupportedWorkspaceSchemaError(
                        "workspace database schema is incomplete or unsupported"
                    )
                self._check_integrity(database)
        except (UnsupportedWorkspaceSchemaError, CorruptWorkspaceDatabaseError):
            raise
        except sqlite3.DatabaseError as exc:
            raise CorruptWorkspaceDatabaseError(
                f"workspace database could not be initialized: {exc}"
            ) from exc

    def _validate_file_header(self) -> None:
        """Reject a non-SQLite file before SQLite can reinterpret it as a database."""
        if not self.path.exists() or self.path.stat().st_size == 0:
            return
        with self.path.open("rb") as handle:
            header = handle.read(16)
        if header != b"SQLite format 3\x00":
            raise CorruptWorkspaceDatabaseError(
                "workspace database file has an invalid SQLite header"
            )

    def transaction(self) -> WorkspaceTransaction:
        """Return a transaction context for atomic workspace metadata writes."""
        return _SqliteWorkspaceTransaction(self)

    def index_record(self, record: WorkspaceRecord) -> None:
        """Atomically register one receipt while preserving receipt identity semantics."""
        try:
            with self.connect() as database:
                database.execute("BEGIN IMMEDIATE")
                values = self._record_values(record)
                row = database.execute(
                    "SELECT record_id, receipt_id, artifact_digest, artifact_size, "
                    "producer_id, producer_type, producer_version, source_ref, "
                    "source_event_id, run_id, captured_at, sensitivity, policy_id, "
                    "verification_status, reliability_state, created_at "
                    "FROM records WHERE record_id = ?",
                    (record.record_id,),
                ).fetchone()
                if record.run_id is not None:
                    self._ensure_observed_run(database, record)
                if row is None:
                    database.execute(
                        "INSERT INTO records "
                        "(record_id, receipt_id, artifact_digest, artifact_size, "
                        "producer_id, producer_type, producer_version, source_ref, "
                        "source_event_id, run_id, captured_at, sensitivity, policy_id, "
                        "verification_status, reliability_state, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        values,
                    )
                elif tuple(row) != values:
                    raise WorkspaceRecordConflictError(
                        f"workspace record identity conflict: {record.record_id}"
                    )
                database.commit()
        except WorkspaceRecordConflictError:
            raise
        except sqlite3.DatabaseError as exc:
            raise CorruptWorkspaceDatabaseError(
                f"workspace record could not be indexed: {exc}"
            ) from exc

    @staticmethod
    def _ensure_observed_run(
        database: sqlite3.Connection, record: WorkspaceRecord
    ) -> None:
        """Ensure a referenced run has a minimal operational index entry."""
        assert record.run_id is not None
        values = (
            record.run_id,
            record.producer_id,
            record.producer_type,
            record.producer_version,
            record.captured_at.astimezone(UTC).isoformat(),
            record.captured_at.astimezone(UTC).isoformat(),
            "observed",
        )
        existing = database.execute(
            "SELECT producer_id, producer_type, producer_version, started_at "
            "FROM runs WHERE run_id = ?",
            (record.run_id,),
        ).fetchone()
        if existing is None:
            database.execute(
                "INSERT INTO runs "
                "(run_id, producer_id, producer_type, producer_version, "
                "started_at, finished_at, status, metadata_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
                values,
            )
            return
        if tuple(existing) != values[1:5]:
            raise WorkspaceRecordConflictError(
                f"workspace run identity conflict: {record.run_id}"
            )

    @staticmethod
    def _record_values(record: WorkspaceRecord) -> tuple[object, ...]:
        """Build database values from the canonical receipt and record metadata."""
        receipt = record.receipt
        captured_at = receipt.captured_at.astimezone(UTC).isoformat()
        created_at = record.created_at.astimezone(UTC).isoformat()
        return (
            record.record_id,
            receipt.receipt_id,
            receipt.artifact_digest,
            receipt.artifact_size,
            receipt.producer_id,
            receipt.producer_type,
            receipt.producer_version,
            receipt.source_ref,
            receipt.source_event_id,
            receipt.run_id,
            captured_at,
            record.sensitivity,
            record.policy_id,
            record.verification_status,
            record.reliability_state,
            created_at,
        )

    def query_records(
        self, query: WorkspaceRecordQuery
    ) -> tuple[tuple[WorkspaceRecordIndexEntry, ...], int]:
        """Return a bounded deterministic page from indexed historical records."""
        clauses: list[str] = []
        parameters: list[object] = []
        if query.record_id is not None:
            clauses.append("record_id = ?")
            parameters.append(query.record_id)
        if query.run_id is not None:
            clauses.append("run_id = ?")
            parameters.append(query.run_id)
        if query.source_event_id is not None:
            clauses.append("source_event_id = ?")
            parameters.append(query.source_event_id)
        if query.producer_id is not None:
            clauses.append("producer_id = ?")
            parameters.append(query.producer_id)
        if query.verification_status is not None:
            clauses.append("verification_status = ?")
            parameters.append(query.verification_status)
        if query.reliability_state is not None:
            clauses.append("reliability_state = ?")
            parameters.append(query.reliability_state)
        if query.sensitivity is not None:
            self._validate_sensitivity(query.sensitivity)
            clauses.append("sensitivity = ?")
            parameters.append(query.sensitivity)
        if query.max_sensitivity is not None:
            self._validate_sensitivity(query.max_sensitivity)
            allowed = tuple(
                sensitivity
                for sensitivity, rank in SENSITIVITY_ORDER.items()
                if rank <= SENSITIVITY_ORDER[query.max_sensitivity]
            )
            placeholders = ", ".join("?" for _ in allowed)
            clauses.append(f"sensitivity IN ({placeholders})")
            parameters.extend(allowed)
        if query.captured_from is not None:
            clauses.append("captured_at >= ?")
            parameters.append(query.captured_from.astimezone(UTC).isoformat())
        if query.captured_to is not None:
            clauses.append("captured_at < ?")
            parameters.append(query.captured_to.astimezone(UTC).isoformat())

        where = "" if not clauses else " WHERE " + " AND ".join(clauses)
        columns = (
            "record_id, receipt_id, artifact_digest, artifact_size, producer_id, "
            "producer_type, producer_version, source_ref, source_event_id, run_id, "
            "captured_at, sensitivity, policy_id, verification_status, "
            "reliability_state, created_at"
        )
        try:
            with self.connect() as database:
                total = int(
                    database.execute(
                        f"SELECT COUNT(*) FROM records{where}", parameters
                    ).fetchone()[0]
                )
                rows = database.execute(
                    f"SELECT {columns} FROM records{where} "
                    "ORDER BY captured_at DESC, record_id DESC LIMIT ? OFFSET ?",
                    (*parameters, query.limit, query.offset),
                ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise CorruptWorkspaceDatabaseError(
                f"workspace records could not be queried: {exc}"
            ) from exc

        entries = tuple(self._entry_from_row(row) for row in rows)
        return entries, total

    @staticmethod
    def _validate_sensitivity(value: str) -> None:
        """Validate one StateWake sensitivity used by a query filter."""
        if value not in SENSITIVITY_ORDER:
            raise ValueError(f"unsupported sensitivity: {value}")

    @staticmethod
    def _entry_from_row(row: tuple[object, ...]) -> WorkspaceRecordIndexEntry:
        """Convert one SQLite row into a typed operational-index entry."""
        return WorkspaceRecordIndexEntry(
            record_id=str(row[0]),
            receipt_id=str(row[1]),
            artifact_digest=str(row[2]),
            artifact_size=int(row[3]),  # type: ignore
            producer_id=str(row[4]),
            producer_type=str(row[5]),
            producer_version=None if row[6] is None else str(row[6]),
            source_ref=str(row[7]),
            source_event_id=None if row[8] is None else str(row[8]),
            run_id=None if row[9] is None else str(row[9]),
            captured_at=parse_datetime(str(row[10]), field="captured_at"),
            sensitivity=str(row[11]),
            policy_id=str(row[12]),
            verification_status=None if row[13] is None else str(row[13]),
            reliability_state=None if row[14] is None else str(row[14]),
            created_at=parse_datetime(str(row[15]), field="created_at"),
        )

    def upsert_retention(
        self,
        *,
        object_id: str,
        policy_id: str,
        sensitivity: str,
        retain_until: str | None,
        legal_hold: bool,
    ) -> None:
        """Persist or replace one durable retention requirement."""
        try:
            with self.connect() as database:
                database.execute(
                    "INSERT INTO retention (object_id, policy_id, sensitivity, retain_until, legal_hold) "
                    "VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(object_id) DO UPDATE SET "
                    "policy_id=excluded.policy_id, sensitivity=excluded.sensitivity, "
                    "retain_until=excluded.retain_until, legal_hold=excluded.legal_hold",
                    (object_id, policy_id, sensitivity, retain_until, int(legal_hold)),
                )
                database.commit()
        except sqlite3.DatabaseError as exc:
            raise CorruptWorkspaceDatabaseError(
                f"workspace retention metadata could not be stored: {exc}"
            ) from exc

    def get_retention(self, object_id: str) -> WorkspaceRetention | None:
        """Return persisted retention metadata for one object."""
        try:
            with self.connect() as database:
                row = database.execute(
                    "SELECT object_id, policy_id, sensitivity, retain_until, legal_hold "
                    "FROM retention WHERE object_id = ?",
                    (object_id,),
                ).fetchone()
        except sqlite3.DatabaseError as exc:
            raise CorruptWorkspaceDatabaseError(
                f"workspace retention metadata could not be read: {exc}"
            ) from exc
        if row is None:
            return None
        return WorkspaceRetention(
            object_id=str(row[0]),
            policy_id=str(row[1]),
            sensitivity=str(row[2]),
            retain_until=None if row[3] is None else str(row[3]),
            legal_hold=bool(row[4]),
        )

    def record_deletion(self, deletion: DeletionRecord) -> None:
        """Persist one payload-free deletion tombstone."""
        try:
            with self.connect() as database:
                database.execute(
                    "INSERT INTO deletions (object_id, digest, sensitivity, deleted_at, policy_id, reason) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        deletion.object_id,
                        deletion.digest,
                        deletion.sensitivity,
                        deletion.deleted_at,
                        deletion.policy_id,
                        deletion.reason,
                    ),
                )
                database.commit()
        except sqlite3.IntegrityError as exc:
            raise WorkspaceRecordConflictError(
                f"workspace deletion identity conflict: {deletion.object_id}"
            ) from exc
        except sqlite3.DatabaseError as exc:
            raise CorruptWorkspaceDatabaseError(
                f"workspace deletion metadata could not be stored: {exc}"
            ) from exc

    def get_deletion(self, object_id: str) -> DeletionRecord | None:
        """Return one payload-free deletion tombstone when present."""
        try:
            with self.connect() as database:
                row = database.execute(
                    "SELECT object_id, digest, sensitivity, deleted_at, policy_id, reason "
                    "FROM deletions WHERE object_id = ?",
                    (object_id,),
                ).fetchone()
        except sqlite3.DatabaseError as exc:
            raise CorruptWorkspaceDatabaseError(
                f"workspace deletion metadata could not be read: {exc}"
            ) from exc
        if row is None:
            return None
        return DeletionRecord(
            object_id=str(row[0]),
            digest=str(row[1]),
            sensitivity=str(row[2]),
            deleted_at=str(row[3]),
            policy_id=str(row[4]),
            reason=str(row[5]),
        )

    def integrity_snapshot(self) -> WorkspaceIntegritySnapshot:
        """Return a consistent read-only snapshot of workspace references."""
        try:
            self._validate_file_header()
            with self.connect() as database:
                version = int(database.execute("PRAGMA user_version").fetchone()[0])
                tables = self._table_names(database)
                indexes = self._index_names(database)
                if (
                    version != SCHEMA_VERSION
                    or tables != EXPECTED_TABLES
                    or indexes != EXPECTED_INDEXES
                ):
                    raise UnsupportedWorkspaceSchemaError(
                        "workspace database schema is incomplete or unsupported"
                    )
                self._check_integrity(database)
                records = tuple(
                    self._entry_from_row(row)
                    for row in database.execute(
                        "SELECT record_id, receipt_id, artifact_digest, artifact_size, "
                        "producer_id, producer_type, producer_version, source_ref, "
                        "source_event_id, run_id, captured_at, sensitivity, policy_id, "
                        "verification_status, reliability_state, created_at "
                        "FROM records ORDER BY captured_at DESC, record_id DESC"
                    ).fetchall()
                )
                run_ids = frozenset(
                    str(row[0])
                    for row in database.execute("SELECT run_id FROM runs").fetchall()
                )
                relationship_rows = tuple(
                    (str(row[0]), str(row[1]), str(row[2]))
                    for row in database.execute(
                        "SELECT source_id, target_id, relationship_type "
                        "FROM relationships ORDER BY source_id, target_id, relationship_type"
                    ).fetchall()
                )
                state_transition_subject_ids = frozenset(
                    str(row[0])
                    for row in database.execute(
                        "SELECT subject_id FROM state_transitions"
                    ).fetchall()
                )
                retention_object_ids = frozenset(
                    str(row[0])
                    for row in database.execute(
                        "SELECT object_id FROM retention"
                    ).fetchall()
                )
                deletion_rows = database.execute(
                    "SELECT object_id, digest, sensitivity, deleted_at, policy_id, reason "
                    "FROM deletions ORDER BY deleted_at, object_id"
                ).fetchall()
                deletion_records = tuple(
                    DeletionRecord(
                        object_id=str(row[0]),
                        digest=str(row[1]),
                        sensitivity=str(row[2]),
                        deleted_at=str(row[3]),
                        policy_id=str(row[4]),
                        reason=str(row[5]),
                    )
                    for row in deletion_rows
                )
                export_rows = database.execute(
                    "SELECT export_id, format, created_at, query_definition_json, "
                    "disclosure_max_sensitivity, source_schema_version, output_path, "
                    "output_digest, row_count FROM exports ORDER BY created_at, export_id"
                ).fetchall()
                exports = tuple(
                    WorkspaceExport(
                        export_id=str(row[0]),
                        format=str(row[1]),
                        created_at=str(row[2]),
                        query_definition_json=str(row[3]),
                        disclosure_max_sensitivity=str(row[4]),
                        source_schema_version=str(row[5]),
                        output_path=str(row[6]),
                        output_digest=None if row[7] is None else str(row[7]),
                        row_count=None if row[8] is None else int(row[8]),
                    )
                    for row in export_rows
                )
        except (UnsupportedWorkspaceSchemaError, CorruptWorkspaceDatabaseError):
            raise
        except sqlite3.DatabaseError as exc:
            raise CorruptWorkspaceDatabaseError(
                f"workspace integrity snapshot could not be read: {exc}"
            ) from exc
        return WorkspaceIntegritySnapshot(
            records=records,
            run_ids=run_ids,
            relationship_rows=relationship_rows,
            state_transition_subject_ids=state_transition_subject_ids,
            retention_object_ids=retention_object_ids,
            deletion_records=deletion_records,
            exports=exports,
        )

    def get_export(self, export_id: str) -> WorkspaceExport | None:
        """Return persisted export metadata for one export identity."""
        try:
            with self.connect() as database:
                row = database.execute(
                    "SELECT export_id, format, created_at, query_definition_json, "
                    "disclosure_max_sensitivity, source_schema_version, output_path, "
                    "output_digest, row_count FROM exports WHERE export_id = ?",
                    (export_id,),
                ).fetchone()
        except sqlite3.DatabaseError as exc:
            raise CorruptWorkspaceDatabaseError(
                f"workspace export metadata could not be read: {exc}"
            ) from exc
        if row is None:
            return None
        return WorkspaceExport(
            export_id=str(row[0]),
            format=str(row[1]),
            created_at=str(row[2]),
            query_definition_json=str(row[3]),
            disclosure_max_sensitivity=str(row[4]),
            source_schema_version=str(row[5]),
            output_path=str(row[6]),
            output_digest=None if row[7] is None else str(row[7]),
            row_count=None if row[8] is None else int(row[8]),
        )

    def list_exports(self, *, limit: int = 1000) -> tuple[WorkspaceExport, ...]:
        """Return recent export metadata in deterministic order."""
        if limit < 1 or limit > 10000:
            raise ValueError("limit must be between 1 and 10000.")
        try:
            with self.connect() as database:
                rows = database.execute(
                    "SELECT export_id, format, created_at, query_definition_json, "
                    "disclosure_max_sensitivity, source_schema_version, output_path, "
                    "output_digest, row_count FROM exports "
                    "ORDER BY created_at DESC, export_id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        except sqlite3.DatabaseError as exc:
            raise CorruptWorkspaceDatabaseError(
                f"workspace export history could not be read: {exc}"
            ) from exc
        return tuple(
            WorkspaceExport(
                export_id=str(row[0]),
                format=str(row[1]),
                created_at=str(row[2]),
                query_definition_json=str(row[3]),
                disclosure_max_sensitivity=str(row[4]),
                source_schema_version=str(row[5]),
                output_path=str(row[6]),
                output_digest=None if row[7] is None else str(row[7]),
                row_count=None if row[8] is None else int(row[8]),
            )
            for row in rows
        )

    def record_export(
        self,
        *,
        export_id: str,
        format_record: str = "parquet",
        created_at: str,
        query_definition_json: str,
        disclosure_max_sensitivity: str,
        source_schema_version: str,
        output_path: str,
        output_digest: str,
        row_count: int,
    ) -> None:
        """Persist metadata for a successfully verified analytical export."""
        try:
            with self.connect() as database:
                database.execute(
                    "INSERT INTO exports "
                    "(export_id, format, created_at, query_definition_json, "
                    "disclosure_max_sensitivity, source_schema_version, output_path, "
                    "output_digest, row_count) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        export_id,
                        format_record,
                        created_at,
                        query_definition_json,
                        disclosure_max_sensitivity,
                        source_schema_version,
                        output_path,
                        output_digest,
                        row_count,
                    ),
                )
                database.commit()
        except sqlite3.IntegrityError as exc:
            raise WorkspaceRecordConflictError(
                f"workspace export identity conflict: {export_id}"
            ) from exc
        except sqlite3.DatabaseError as exc:
            raise CorruptWorkspaceDatabaseError(
                f"workspace export metadata could not be stored: {exc}"
            ) from exc

    def get_workspace_identity(self) -> WorkspaceIdentity:
        """Read and validate the single workspace identity row."""
        try:
            with self.connect() as database:
                row = database.execute(
                    "SELECT workspace_id, schema_version, created_at, "
                    "statewake_version, public_api_contract FROM workspace"
                ).fetchone()
        except sqlite3.DatabaseError as exc:
            raise CorruptWorkspaceDatabaseError(
                f"workspace metadata could not be read: {exc}"
            ) from exc
        if row is None:
            raise CorruptWorkspaceDatabaseError("workspace metadata row is missing")
        return WorkspaceIdentity(
            workspace_id=str(row[0]),
            created_at=str(row[2]),
            schema_version=str(row[1]),
            statewake_public_api_contract_version=str(row[4]),
        )

    def connect(self) -> sqlite3.Connection:
        """Open a configured SQLite connection."""
        database = sqlite3.connect(self.path, timeout=30.0)
        database.execute("PRAGMA foreign_keys=ON")
        database.execute("PRAGMA journal_mode=WAL")
        database.execute("PRAGMA synchronous=FULL")
        return database

    @staticmethod
    def _table_names(database: sqlite3.Connection) -> frozenset[str]:
        """Return deterministic names of user tables in the database."""
        rows = database.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return frozenset(str(row[0]) for row in rows)

    @staticmethod
    def _index_names(database: sqlite3.Connection) -> frozenset[str]:
        """Return deterministic names of application-defined indexes."""
        rows = database.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='index' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return frozenset(str(row[0]) for row in rows)

    @staticmethod
    def _check_integrity(database: sqlite3.Connection) -> None:
        """Raise a classified error when SQLite integrity checking fails."""
        result = database.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            detail = (
                "unknown integrity-check failure" if result is None else str(result[0])
            )
            raise CorruptWorkspaceDatabaseError(
                f"workspace database integrity check failed: {detail}"
            )


class _SqliteWorkspaceTransaction(WorkspaceTransaction):
    """Transaction implementation for workspace metadata."""

    def __init__(self, repository: SqliteWorkspaceRepository) -> None:
        """Initialize a transaction bound to a repository."""
        self._repository = repository
        self._database: sqlite3.Connection | None = None

    def __enter__(self) -> _SqliteWorkspaceTransaction:
        """Open the transaction and return its typed transaction handle."""
        self._database = self._repository.connect()
        try:
            self._database.execute("BEGIN IMMEDIATE")
        except sqlite3.DatabaseError as exc:
            self._database.close()
            self._database = None
            raise CorruptWorkspaceDatabaseError(
                f"workspace transaction could not begin: {exc}"
            ) from exc
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object | None,
    ) -> None:
        """Commit on success or roll back when the transaction fails."""
        database = self._database
        self._database = None
        if database is None:
            return
        try:
            if exc_type is None:
                database.commit()
            else:
                database.rollback()
        finally:
            database.close()

    def set_workspace_metadata(
        self, identity: WorkspaceIdentity, statewake_version: str
    ) -> None:
        """Insert or idempotently validate workspace metadata."""
        database = self._require_database()
        try:
            row = database.execute(
                "SELECT workspace_id, schema_version, created_at, "
                "statewake_version, public_api_contract FROM workspace"
            ).fetchone()
            values = (
                identity.workspace_id,
                identity.schema_version,
                identity.created_at,
                statewake_version,
                identity.statewake_public_api_contract_version,
            )
            if row is None:
                database.execute(
                    "INSERT INTO workspace "
                    "(workspace_id, schema_version, created_at, statewake_version, public_api_contract) "
                    "VALUES (?, ?, ?, ?, ?)",
                    values,
                )
                return
            if tuple(row) != values:
                raise CorruptWorkspaceDatabaseError(
                    "workspace metadata does not match the workspace identity"
                )
        except CorruptWorkspaceDatabaseError:
            raise
        except sqlite3.IntegrityError as exc:
            raise CorruptWorkspaceDatabaseError(
                f"workspace metadata could not be stored: {exc}"
            ) from exc
        except sqlite3.DatabaseError as exc:
            raise CorruptWorkspaceDatabaseError(
                f"workspace metadata could not be stored: {exc}"
            ) from exc

    def _require_database(self) -> sqlite3.Connection:
        """Return the active transaction connection or fail clearly."""
        if self._database is None:
            raise RuntimeError("workspace transaction is not active")
        return self._database


__all__ = ["SqliteWorkspaceRepository"]
