"""Regression tests for Tier 10 JSON and portable dataset exports."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from zipfile import ZipFile

import pytest

from statewake.workspace import StateWakeWorkspace, WorkspaceRecordQuery
from statewake.workspace.json_export import JsonExportError, verify_json, write_json
from statewake.workspace.portable_bundle import (
    PortableBundleError,
    verify_portable_bundle,
    write_portable_bundle,
)
from statewake.workspace.projections import DatasetProjection


def test_json_export_is_canonical_and_reopenable(tmp_path: Path) -> None:
    workspace = StateWakeWorkspace.open(tmp_path / "workspace")
    workspace.ingest(
        b"json",
        producer_type="test",
        producer_id="producer",
        source_ref="source",
        captured_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
    )
    projection = workspace.project(WorkspaceRecordQuery(limit=10))
    result = write_json(
        projection,
        tmp_path / "records.json",
        schema_version="1",
        disclosure_max_sensitivity="internal",
        query_definition={"limit": 10},
    )
    verify_json(result.output_path, expected_rows=1, expected_schema_version="1")
    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert payload["format"] == "json"
    assert payload["dataset"] == projection.to_dict()


def test_json_export_is_byte_stable(tmp_path: Path) -> None:
    workspace = StateWakeWorkspace.open(tmp_path / "workspace")
    workspace.ingest(
        b"stable",
        producer_type="test",
        producer_id="producer",
        source_ref="source",
        captured_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
    )
    projection = workspace.project(WorkspaceRecordQuery(limit=10))
    first = write_json(
        projection,
        tmp_path / "first.json",
        schema_version="1",
        disclosure_max_sensitivity="internal",
        query_definition={"limit": 10},
    )
    second = write_json(
        projection,
        tmp_path / "second.json",
        schema_version="1",
        disclosure_max_sensitivity="internal",
        query_definition={"limit": 10},
    )
    assert first.output_digest == second.output_digest
    assert first.output_path.read_bytes() == second.output_path.read_bytes()


def test_json_verifier_rejects_wrong_dataset_shape(tmp_path: Path) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(
        json.dumps(
            {
                "format": "json",
                "schema_version": "1",
                "disclosure_max_sensitivity": "internal",
                "query": {},
                "dataset": {"records": "not-a-list"},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(JsonExportError, match="records must be an array"):
        verify_json(path, expected_rows=0, expected_schema_version="1")


def test_workspace_json_export_records_history_and_matches_projection(
    tmp_path: Path,
) -> None:
    with StateWakeWorkspace.open(tmp_path / "workspace") as workspace:
        workspace.ingest(
            b"one",
            producer_type="test",
            producer_id="producer",
            source_ref="source-1",
            captured_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        query = WorkspaceRecordQuery(limit=1)
        projection = workspace.project(query)
        result = workspace.export_json(query, tmp_path / "records.json")
        database_path = workspace.configuration.database_path

    with sqlite3.connect(database_path) as database:
        history = database.execute(
            "SELECT format, row_count, source_schema_version FROM exports "
            "WHERE export_id = ?",
            (result.export_id,),
        ).fetchone()
    payload = json.loads(result.output_path.read_text(encoding="utf-8"))
    assert payload["dataset"] == projection.to_dict()
    assert history == ("json", 1, "1")


def test_portable_bundle_is_self_describing_and_verified(tmp_path: Path) -> None:
    workspace = StateWakeWorkspace.open(tmp_path / "workspace")
    record = workspace.ingest(
        b"bundle",
        producer_type="test",
        producer_id="producer",
        source_ref="source",
        captured_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
    )
    projection = workspace.project(WorkspaceRecordQuery(limit=10))
    result = write_portable_bundle(
        projection,
        (record,),
        tmp_path / "bundle.zip",
        workspace_id=workspace.identity.workspace_id,
        schema_version="1",
        disclosure_max_sensitivity="internal",
        query_definition={"limit": 10},
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    verify_portable_bundle(
        result.output_path,
        expected_rows=1,
        expected_schema_version="1",
        expected_workspace_id=workspace.identity.workspace_id,
    )
    with ZipFile(result.output_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["proof_bundle"] is False
        assert set(archive.namelist()) == {
            "README.md",
            "checksums.json",
            "dataset.json",
            "manifest.json",
            "receipts.jsonl",
            "state.jsonl",
        }


def test_portable_bundle_rejects_checksum_tampering(tmp_path: Path) -> None:
    workspace = StateWakeWorkspace.open(tmp_path / "workspace")
    record = workspace.ingest(
        b"bundle",
        producer_type="test",
        producer_id="producer",
        source_ref="source",
        captured_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    projection = DatasetProjection.from_query_page(
        workspace.query(WorkspaceRecordQuery(limit=10))
    )
    result = write_portable_bundle(
        projection,
        (record,),
        tmp_path / "bundle.zip",
        workspace_id=workspace.identity.workspace_id,
        schema_version="1",
        disclosure_max_sensitivity="internal",
        query_definition={},
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    raw = result.output_path.read_bytes()
    with ZipFile(result.output_path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    members["dataset.json"] += b"tampered"
    with result.output_path.open("wb") as handle:
        from zipfile import ZIP_DEFLATED, ZipInfo

        with ZipFile(handle, "w", compression=ZIP_DEFLATED) as archive:
            for name, content in sorted(members.items()):
                info = ZipInfo(name)
                info.date_time = (1980, 1, 1, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, content)
    assert raw != result.output_path.read_bytes()
    with pytest.raises(PortableBundleError, match="checksum mismatch"):
        verify_portable_bundle(
            result.output_path,
            expected_rows=1,
            expected_schema_version="1",
            expected_workspace_id=workspace.identity.workspace_id,
        )
