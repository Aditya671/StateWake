"""Read-API regressions for data governance lifecycle investigation."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from statewake.domain.data_lifecycle import DataLifecyclePolicy
from statewake.domain.governance import (
    EvidenceGovernancePolicy,
    PrivacyGovernanceRuntimeConfig,
)
from statewake.domain.privacy import PrivacyPolicy
from statewake.read_api import ReadApiConfig, create_read_application
from statewake.services.data_lifecycle_investigation_service import (
    DATA_LIFECYCLE_CONTEXT_SCHEMA_VERSION,
)
from statewake.services.privacy_governance_runtime_service import (
    write_privacy_governance_runtime_snapshot,
)
from statewake.workspace import StateWakeWorkspace

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def _require_header_list(value: object) -> list[tuple[str, str]]:
    """Narrow captured WSGI headers before converting them to a mapping."""
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
    query_string: str = "",
    if_none_match: str | None = None,
) -> tuple[str, dict[str, str], bytes]:
    environ: dict[str, object] = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "QUERY_STRING": query_string,
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

    body = b"".join(application(environ, start_response))
    return (
        str(captured["status"]),
        dict(_require_header_list(captured.get("headers"))),
        body,
    )


def _policy() -> DataLifecyclePolicy:
    return DataLifecyclePolicy(
        policy_id="ui-governance",
        purpose="operator-lifecycle-investigation",
        max_retention_days=0,
        storage_max_sensitivity="restricted",
        telemetry_max_sensitivity="internal",
        disclosure_max_sensitivity="internal",
        encryption_at_rest_required=True,
        tls_required=True,
    )


def _context_payload(
    *,
    record_id: str,
    sensitivity: str,
    created_at: datetime,
    policy: DataLifecyclePolicy,
    legal_hold: bool,
) -> dict[str, object]:
    return {
        "schema_version": DATA_LIFECYCLE_CONTEXT_SCHEMA_VERSION,
        "object_kind": "workspace-record",
        "object_id": record_id,
        "sensitivity": sensitivity,
        "created_at": created_at.isoformat(),
        "legal_hold": legal_hold,
        "policy": {
            "policy_id": policy.policy_id,
            "purpose": policy.purpose,
            "max_retention_days": policy.max_retention_days,
            "storage_max_sensitivity": policy.storage_max_sensitivity,
            "telemetry_max_sensitivity": policy.telemetry_max_sensitivity,
            "disclosure_max_sensitivity": policy.disclosure_max_sensitivity,
            "encryption_at_rest_required": policy.encryption_at_rest_required,
            "tls_required": policy.tls_required,
        },
        "recorded_decision": None,
    }


def _configured_workspace(
    tmp_path: Path,
    *,
    legal_hold: bool = True,
) -> tuple[Path, Path, str]:
    root = tmp_path / "workspace"
    policy = _policy()
    with StateWakeWorkspace.open(root) as workspace:
        record = workspace.ingest(
            b"governed-api-payload",
            producer_type="test",
            producer_id="producer",
            source_ref="source",
            captured_at=BASE,
        )
        workspace.apply_retention(
            record.record_id,
            policy,
            legal_hold=legal_hold,
            now=BASE,
        )
    context = tmp_path / "lifecycle-context.json"
    context.write_text(
        json.dumps(
            _context_payload(
                record_id=record.record_id,
                sensitivity=record.sensitivity,
                created_at=record.created_at,
                policy=policy,
                legal_hold=legal_hold,
            )
        ),
        encoding="utf-8",
    )
    return root, context, record.record_id


def test_data_governance_route_replays_policy_and_preserves_legal_hold(
    tmp_path: Path,
) -> None:
    root, context, record_id = _configured_workspace(tmp_path, legal_hold=True)
    application = create_read_application(
        ReadApiConfig(root, data_lifecycle_context_path=context)
    )
    status, headers, raw = _request(application, "/api/v1/data-governance")
    payload = json.loads(raw)
    assert status == "200 OK"
    assert payload["schema_version"] == "data-governance-investigation.v2"
    assert payload["durable_retention"]["legal_hold"] is True
    assert payload["current_decision"]["expired"] is True
    assert payload["current_decision"]["deletion_allowed"] is False
    assert payload["current_decision"]["policy_replay_verified"] is True
    assert (
        payload["confidentiality_requirements"][
            "host_requirement_satisfaction_evaluated"
        ]
        is False
    )
    assert context.as_posix() not in raw.decode("utf-8")
    assert record_id not in raw.decode("utf-8")
    assert headers["ETag"].startswith('"')


def test_data_governance_route_supports_conditional_read(tmp_path: Path) -> None:
    root, context, _ = _configured_workspace(tmp_path, legal_hold=True)
    application = create_read_application(
        ReadApiConfig(root, data_lifecycle_context_path=context)
    )
    status, headers, _ = _request(application, "/api/v1/data-governance")
    assert status == "200 OK"
    etag = headers["ETag"]
    status, returned_headers, raw = _request(
        application,
        "/api/v1/data-governance",
        if_none_match=etag,
    )
    assert status == "304 Not Modified"
    assert returned_headers["ETag"] == etag
    assert raw == b""


def test_data_governance_capability_is_configured_only_with_context(
    tmp_path: Path,
) -> None:
    root, context, _ = _configured_workspace(tmp_path)
    configured = create_read_application(
        ReadApiConfig(root, data_lifecycle_context_path=context)
    )
    status, _, raw = _request(configured, "/api/v1/capabilities")
    assert status == "200 OK"
    assert json.loads(raw)["features"]["data_governance_read"] is True

    unconfigured = create_read_application(ReadApiConfig(root))
    status, _, raw = _request(unconfigured, "/api/v1/capabilities")
    assert status == "200 OK"
    assert json.loads(raw)["features"]["data_governance_read"] is False
    status, _, raw = _request(unconfigured, "/api/v1/data-governance")
    assert status == "404 Not Found"
    assert json.loads(raw)["error"]["code"] == "DATA_GOVERNANCE_SOURCE_NOT_CONFIGURED"


def test_data_governance_route_rejects_workspace_context_mismatch(
    tmp_path: Path,
) -> None:
    root, context, _ = _configured_workspace(tmp_path, legal_hold=True)
    payload = json.loads(context.read_text(encoding="utf-8"))
    payload["legal_hold"] = False
    context.write_text(json.dumps(payload), encoding="utf-8")
    application = create_read_application(
        ReadApiConfig(root, data_lifecycle_context_path=context)
    )
    status, _, raw = _request(application, "/api/v1/data-governance")
    assert status == "422 Unprocessable Entity"
    assert json.loads(raw)["error"]["code"] == "INVALID_DATA_GOVERNANCE_SOURCE"


def test_data_governance_route_rejects_oversized_source_and_query(
    tmp_path: Path,
) -> None:
    root, context, _ = _configured_workspace(tmp_path)
    application = create_read_application(
        ReadApiConfig(
            root,
            data_lifecycle_context_path=context,
            max_data_lifecycle_context_bytes=8,
        )
    )
    status, _, raw = _request(application, "/api/v1/data-governance")
    assert status == "413 Request Entity Too Large"
    assert json.loads(raw)["error"]["code"] == "DATA_GOVERNANCE_SOURCE_TOO_LARGE"

    application = create_read_application(
        ReadApiConfig(root, data_lifecycle_context_path=context)
    )
    status, _, raw = _request(
        application,
        "/api/v1/data-governance",
        query_string="path=/tmp/secret",
    )
    assert status == "400 Bad Request"
    assert json.loads(raw)["error"]["code"] == "INVALID_DATA_GOVERNANCE_QUERY"


def test_data_governance_route_includes_digest_verified_runtime_privacy_snapshot(
    tmp_path: Path,
) -> None:
    root, context, _ = _configured_workspace(tmp_path, legal_hold=False)
    snapshot = tmp_path / "privacy-governance.json"
    runtime = PrivacyGovernanceRuntimeConfig(
        privacy_policy=PrivacyPolicy(policy_id="privacy-runtime"),
        evidence_policy=EvidenceGovernancePolicy(
            policy_id="evidence-runtime",
            storage_max_sensitivity="confidential",
            telemetry_max_sensitivity="internal",
        ),
    )
    write_privacy_governance_runtime_snapshot(snapshot, runtime)
    application = create_read_application(
        ReadApiConfig(
            root,
            data_lifecycle_context_path=context,
            privacy_governance_snapshot_path=snapshot,
        )
    )
    status, _, raw = _request(application, "/api/v1/data-governance")
    payload = json.loads(raw)
    assert status == "200 OK"
    runtime_view = payload["privacy_governance_runtime"]
    assert runtime_view["observed"] is True
    assert runtime_view["privacy_policy"]["policy_id"] == "privacy-runtime"
    assert runtime_view["evidence_policy"]["policy_id"] == "evidence-runtime"
    assert (
        runtime_view["evidence_policy"]["storage_governance_before_artifact_write"]
        is True
    )
    assert (
        runtime_view["evidence_policy"]["telemetry_runtime_binding_observed"] is False
    )
    assert runtime_view["opaque_content_secret_scanning"] is False
    assert snapshot.as_posix() not in raw.decode("utf-8")


def test_data_governance_route_rejects_tampered_runtime_privacy_snapshot(
    tmp_path: Path,
) -> None:
    root, context, _ = _configured_workspace(tmp_path, legal_hold=False)
    snapshot = tmp_path / "privacy-governance.json"
    runtime = PrivacyGovernanceRuntimeConfig(
        privacy_policy=PrivacyPolicy(policy_id="privacy-runtime"),
        evidence_policy=EvidenceGovernancePolicy(policy_id="evidence-runtime"),
    )
    write_privacy_governance_runtime_snapshot(snapshot, runtime)
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    payload["enforcement"]["opaque_content_secret_scanning"] = True
    snapshot.write_text(json.dumps(payload), encoding="utf-8")
    application = create_read_application(
        ReadApiConfig(
            root,
            data_lifecycle_context_path=context,
            privacy_governance_snapshot_path=snapshot,
        )
    )
    status, _, raw = _request(application, "/api/v1/data-governance")
    assert status == "422 Unprocessable Entity"
    assert json.loads(raw)["error"]["code"] == "INVALID_DATA_GOVERNANCE_SOURCE"
