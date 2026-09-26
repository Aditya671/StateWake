"""Versioned SQLite schema for the StateWake operational workspace index."""

from __future__ import annotations

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE workspace (
    workspace_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    statewake_version TEXT NOT NULL,
    public_api_contract TEXT NOT NULL
);

CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    producer_id TEXT NOT NULL,
    producer_type TEXT NOT NULL,
    producer_version TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    metadata_json TEXT
);

CREATE TABLE records (
    record_id TEXT PRIMARY KEY,
    receipt_id TEXT,
    artifact_digest TEXT,
    artifact_size INTEGER,
    producer_id TEXT NOT NULL,
    producer_type TEXT NOT NULL,
    producer_version TEXT,
    source_ref TEXT,
    source_event_id TEXT,
    run_id TEXT,
    captured_at TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    policy_id TEXT,
    verification_status TEXT,
    reliability_state TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE relationships (
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (source_id, target_id, relationship_type)
);

CREATE TABLE state_transitions (
    transition_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    from_state TEXT,
    to_state TEXT NOT NULL,
    previous_digest TEXT,
    current_digest TEXT,
    occurred_at TEXT NOT NULL
);

CREATE TABLE retention (
    object_id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    retain_until TEXT,
    legal_hold INTEGER NOT NULL
);

CREATE TABLE exports (
    export_id TEXT PRIMARY KEY,
    format TEXT NOT NULL,
    created_at TEXT NOT NULL,
    query_definition_json TEXT NOT NULL,
    disclosure_max_sensitivity TEXT NOT NULL,
    source_schema_version TEXT NOT NULL,
    output_path TEXT NOT NULL,
    output_digest TEXT,
    row_count INTEGER
);

CREATE TABLE deletions (
    object_id TEXT PRIMARY KEY,
    digest TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    deleted_at TEXT NOT NULL,
    policy_id TEXT NOT NULL,
    reason TEXT NOT NULL
);

CREATE INDEX idx_runs_producer_started
    ON runs (producer_id, started_at, run_id);
CREATE INDEX idx_records_producer_captured
    ON records (producer_id, captured_at, record_id);
CREATE INDEX idx_records_run_captured
    ON records (run_id, captured_at, record_id);
CREATE INDEX idx_records_artifact_digest
    ON records (artifact_digest);
CREATE INDEX idx_records_receipt_id
    ON records (receipt_id);
CREATE INDEX idx_relationships_target
    ON relationships (target_id, relationship_type, source_id);
CREATE INDEX idx_state_transitions_subject_occurred
    ON state_transitions (subject_id, occurred_at, transition_id);
CREATE INDEX idx_retention_policy
    ON retention (policy_id, retain_until, object_id);
CREATE INDEX idx_exports_created
    ON exports (created_at, export_id);
CREATE INDEX idx_deletions_deleted_at
    ON deletions (deleted_at, object_id);
"""

EXPECTED_INDEXES = frozenset(
    {
        "idx_runs_producer_started",
        "idx_records_producer_captured",
        "idx_records_run_captured",
        "idx_records_artifact_digest",
        "idx_records_receipt_id",
        "idx_relationships_target",
        "idx_state_transitions_subject_occurred",
        "idx_retention_policy",
        "idx_exports_created",
        "idx_deletions_deleted_at",
    }
)

EXPECTED_TABLES = frozenset(
    {
        "workspace",
        "runs",
        "records",
        "relationships",
        "state_transitions",
        "retention",
        "exports",
        "deletions",
    }
)


__all__ = ["EXPECTED_INDEXES", "EXPECTED_TABLES", "SCHEMA_SQL", "SCHEMA_VERSION"]
