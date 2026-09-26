from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path

import pytest

from statewake.workspace.csv_export import (
    CSV_NULL,
    CSV_RECORD_COLUMNS,
    CsvExportError,
    verify_csv,
    write_csv,
)
from statewake.workspace.projections import NormalizedRecordProjection


def _record() -> NormalizedRecordProjection:
    return NormalizedRecordProjection(
        record_id="record-1",
        receipt_id="receipt-1",
        artifact_digest="a" * 64,
        artifact_size=4,
        producer_id="producer-1",
        producer_type="test",
        producer_version=None,
        source_ref="source,with,commas",
        source_event_id=None,
        run_id=None,
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        sensitivity="internal",
        policy_id="default",
        verification_status=None,
        reliability_state=None,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_csv_write_and_reopen_round_trip(tmp_path: Path) -> None:
    result = write_csv(
        [_record()],
        tmp_path / "records.csv",
        schema_version="1",
        disclosure_max_sensitivity="internal",
        query_definition={"limit": 1},
    )
    verify_csv(result.output_path, expected_rows=1, expected_schema_version="1")
    with result.output_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert tuple(rows[0]) == CSV_RECORD_COLUMNS
    assert rows[1][6] == CSV_NULL
    assert rows[1][8] == CSV_NULL
    assert rows[1][7] == "source,with,commas"


def test_csv_rejects_wrong_header(tmp_path: Path) -> None:
    path = tmp_path / "records.csv"
    path.write_text("wrong\nvalue\n", encoding="utf-8")
    with pytest.raises(CsvExportError, match="schema mismatch"):
        verify_csv(path, expected_rows=1, expected_schema_version="1")


def test_csv_rejects_unencoded_empty_value(tmp_path: Path) -> None:
    path = tmp_path / "records.csv"
    values = ["x"] * len(CSV_RECORD_COLUMNS)
    values[6] = ""
    path.write_text(
        ",".join(CSV_RECORD_COLUMNS) + "\n" + ",".join(values) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(CsvExportError, match="unencoded null"):
        verify_csv(path, expected_rows=1, expected_schema_version="1")


def test_workspace_csv_export_matches_selected_projection_page(tmp_path: Path) -> None:
    from statewake.workspace import StateWakeWorkspace, WorkspaceRecordQuery

    with StateWakeWorkspace.open(tmp_path / "workspace") as workspace:
        workspace.ingest(
            b"one",
            producer_type="test",
            producer_id="producer",
            source_ref="source-1",
            captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        workspace.ingest(
            b"two",
            producer_type="test",
            producer_id="producer",
            source_ref="source-2",
            captured_at=datetime(2026, 1, 2, tzinfo=UTC),
        )
        query = WorkspaceRecordQuery(limit=1)
        projection = workspace.project(query)
        result = workspace.export_csv(query, tmp_path / "records.csv")

    assert result.row_count == len(projection.records) == 1
    with result.output_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[1][0] == projection.records[0].record_id


def test_workspace_csv_export_applies_disclosure_ceiling(tmp_path: Path) -> None:
    from statewake.workspace import StateWakeWorkspace, WorkspaceRecordQuery

    with StateWakeWorkspace.open(tmp_path / "workspace") as workspace:
        workspace.ingest(
            b"one",
            producer_type="test",
            producer_id="producer",
            source_ref="source-1",
            captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        result = workspace.export_csv(
            WorkspaceRecordQuery(max_sensitivity="internal"),
            tmp_path / "records.csv",
            max_sensitivity="internal",
        )

    assert result.disclosure_max_sensitivity == "internal"
