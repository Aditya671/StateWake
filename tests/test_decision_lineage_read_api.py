"""Read-API regressions for reliability decision/reconciliation/lineage investigation."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

from statewake.read_api import ReadApiConfig, create_read_application
from statewake.services.reliability_evidence_service import (
    write_reliability_evidence_chain,
)
from statewake.workspace.workspace import StateWakeWorkspace
from tests.presentation.test_decision_lineage import decision_chain_fixture


def _require_header_list(value: object) -> list[tuple[str, str]]:
    """Narrow captured WSGI response headers for type-safe test assertions."""
    assert isinstance(value, list)
    assert all(
        isinstance(item, tuple)
        and len(item) == 2
        and isinstance(item[0], str)
        and isinstance(item[1], str)
        for item in value
    )
    return [(item[0], item[1]) for item in value]


def _request(
    application: Any,
    path: str,
    *,
    if_none_match: str | None = None,
) -> tuple[str, dict[str, str], bytes]:
    environ: dict[str, object] = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "QUERY_STRING": "",
        "CONTENT_LENGTH": "0",
        "wsgi.input": io.BytesIO(b""),
        "wsgi.url_scheme": "http",
    }
    if if_none_match is not None:
        environ["HTTP_IF_NONE_MATCH"] = if_none_match
    captured: dict[str, object] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        captured["status"] = status
        captured["headers"] = headers

    raw = b"".join(application(environ, start_response))
    return (
        str(captured["status"]),
        dict(_require_header_list(captured.get("headers"))),
        raw,
    )


def _configured(tmp_path: Path, **changes: object) -> tuple[ReadApiConfig, Path]:
    root = tmp_path / "evidence"
    root.mkdir(parents=True)
    chain, _ = decision_chain_fixture(root)
    chain_path = root / "chain.json"
    write_reliability_evidence_chain(chain, chain_path)
    workspace = tmp_path / "workspace"
    opened = StateWakeWorkspace.open(workspace)
    opened.close()
    values: dict[str, object] = {
        "workspace_root": workspace,
        "reliability_decision_chain_path": chain_path,
    }
    values.update(changes)
    return ReadApiConfig(**values), chain_path  # type: ignore[arg-type]


def test_decision_lineage_endpoint_and_conditional_read(tmp_path: Path) -> None:
    config, _ = _configured(tmp_path)
    application = create_read_application(config)
    status, headers, raw = _request(application, "/api/v1/decision-lineage")
    payload = json.loads(raw)
    assert status == "200 OK"
    assert payload["schema_version"] == "decision-lineage-investigation.v1"
    assert payload["decision_basis"]["present"] is True
    assert payload["lineage"]["verified"] is True
    assert str(tmp_path) not in raw.decode("utf-8")

    status, second_headers, body = _request(
        application,
        "/api/v1/decision-lineage",
        if_none_match=headers["ETag"],
    )
    assert status == "304 Not Modified"
    assert second_headers["ETag"] == headers["ETag"]
    assert body == b""


def test_decision_lineage_capability_and_unconfigured_state(tmp_path: Path) -> None:
    config, _ = _configured(tmp_path)
    application = create_read_application(config)
    status, _, raw = _request(application, "/api/v1/capabilities")
    assert status == "200 OK"
    assert json.loads(raw)["features"]["decision_lineage_read"] is True

    empty = create_read_application(ReadApiConfig(tmp_path / "workspace-empty"))
    status, _, raw = _request(empty, "/api/v1/decision-lineage")
    assert status == "404 Not Found"
    assert json.loads(raw)["error"]["code"] == "DECISION_LINEAGE_SOURCE_NOT_CONFIGURED"


def test_decision_lineage_rejects_tampered_reference(tmp_path: Path) -> None:
    config, chain_path = _configured(tmp_path)
    payload = json.loads(chain_path.read_text())
    evidence_source = chain_path.parent / payload["evidence"][0]["source"]
    evidence_source.write_text('{"tampered":true}', encoding="utf-8")
    status, _, raw = _request(
        create_read_application(config), "/api/v1/decision-lineage"
    )
    assert status == "422 Unprocessable Entity"
    assert json.loads(raw)["error"]["code"] == "INVALID_DECISION_LINEAGE_SOURCE"


def test_decision_lineage_enforces_chain_and_aggregate_bounds(tmp_path: Path) -> None:
    config, _ = _configured(tmp_path, max_decision_chain_bytes=1)
    status, _, raw = _request(
        create_read_application(config), "/api/v1/decision-lineage"
    )
    assert status == "413 Request Entity Too Large"
    assert json.loads(raw)["error"]["code"] == "DECISION_LINEAGE_SOURCE_TOO_LARGE"

    config, _ = _configured(tmp_path / "second", max_decision_source_bytes=1)
    status, _, raw = _request(
        create_read_application(config), "/api/v1/decision-lineage"
    )
    assert status == "413 Request Entity Too Large"
    assert json.loads(raw)["error"]["code"] == "DECISION_LINEAGE_SOURCE_TOO_LARGE"
