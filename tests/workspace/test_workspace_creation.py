"""Tests for StateWake workspace creation and manifest persistence."""

import json
from pathlib import Path

import pytest

import statewake
from statewake.workspace import (
    StateWakeWorkspace,
    WorkspaceError,
    WorkspaceSchemaError,
)


def test_workspace_can_be_created_in_empty_directory(tmp_path: Path) -> None:
    """Create a complete workspace directory and manifest."""
    workspace = StateWakeWorkspace.open(tmp_path / ".statewake")

    assert workspace.root.is_dir()
    assert workspace.configuration.manifest_path.is_file()
    assert workspace.configuration.database_path == workspace.root / "statewake.db"
    for directory in workspace.configuration.required_directories():
        assert directory.is_dir()

    manifest = json.loads(
        workspace.configuration.manifest_path.read_text(encoding="utf-8")
    )
    assert manifest["workspace_id"] == workspace.identity.workspace_id
    assert manifest["schema_version"] == "1"
    assert manifest["statewake_version"] == statewake.__version__
    assert manifest["public_api_contract_version"] == "1"


def test_workspace_can_be_reopened_without_replacing_identity(tmp_path: Path) -> None:
    """Reopening a workspace preserves its durable identity and manifest."""
    root = tmp_path / ".statewake"
    first = StateWakeWorkspace.open(root)
    manifest_before = first.configuration.manifest_path.read_text(encoding="utf-8")
    first.close()

    second = StateWakeWorkspace.open(root)

    assert second.identity == first.identity
    assert (
        second.configuration.manifest_path.read_text(encoding="utf-8")
        == manifest_before
    )


def test_workspace_context_manager_closes_without_deleting_state(
    tmp_path: Path,
) -> None:
    """Closing a workspace must not delete its durable directory."""
    root = tmp_path / ".statewake"
    with StateWakeWorkspace.open(root) as workspace:
        workspace_id = workspace.identity.workspace_id

    assert workspace.closed
    assert root.is_dir()
    reopened = StateWakeWorkspace.open(root)
    assert reopened.identity.workspace_id == workspace_id


def test_workspace_rejects_file_as_root(tmp_path: Path) -> None:
    """A file cannot be used as a workspace root."""
    root = tmp_path / "workspace"
    root.write_text("not a directory", encoding="utf-8")

    with pytest.raises(WorkspaceError, match="not a directory"):
        StateWakeWorkspace.open(root)


def test_workspace_rejects_unsupported_schema(tmp_path: Path) -> None:
    """An existing unsupported workspace schema is not silently reinterpreted."""
    root = tmp_path / ".statewake"
    root.mkdir()
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "workspace_id": "workspace-1",
                "schema_version": "999",
                "statewake_version": "0.1.0",
                "public_api_contract_version": "1",
                "created_at": "2026-09-16T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(WorkspaceSchemaError, match="unsupported workspace schema"):
        StateWakeWorkspace.open(root)
