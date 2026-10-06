"""End-to-end regressions for the operational trust and validation frontier."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from statewake.adapters.human_approval import WorkspaceHumanApprovalStore
from statewake.read_api import ReadApiConfig, create_read_application
from statewake.release_trust import (
    ArtifactDigest,
    BuildProvenance,
    ExternalEvidence,
    HumanReleaseDecision,
    PublicationExecutionPermit,
    RegistryPublicationLifecycleStore,
    RegistryPublicationReceipt,
    RegistryPublishedArtifact,
    ReleaseTrustBundle,
    SourceIdentity,
    publication_basis_from_release_trust,
    reconcile_registry_publication_lifecycle,
    record_publication_authorization,
    revoke_publication_authorization,
    write_publication_execution_permit,
    write_registry_publication_receipt,
    write_release_publication_basis,
    write_release_trust_bundle,
)
from statewake.validation_study import run_comparative_validation_study
from statewake.validation_study.model import canonical_digest
from statewake.validation_study.report import render_study_json
from statewake.workspace import StateWakeWorkspace


def _request(
    application: Any,
    path: str,
    query: str = "",
    *,
    if_none_match: str | None = None,
) -> tuple[str, dict[str, str], dict[str, object]]:
    environ: dict[str, object] = {
        "REQUEST_METHOD": "GET",
        "PATH_INFO": path,
        "QUERY_STRING": query,
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
    payload = json.loads(raw) if raw else {}
    headers = cast(list[tuple[str, str]], captured["headers"])
    return str(captured["status"]), dict(headers), cast(dict[str, object], payload)


def _write(root: Path, relative: str, content: bytes) -> tuple[str, int]:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return sha256(content).hexdigest(), len(content)


def _release_fixture(tmp_path: Path) -> tuple[Path, Path, ReleaseTrustBundle]:
    root = tmp_path / "release"
    wheel_digest, wheel_size = _write(
        root, "statewake_ai-0.4.1-py3-none-any.whl", b"wheel"
    )
    tests_digest, _ = _write(root, "release-trust/tests.json", b"tests")
    sbom_digest, _ = _write(root, "release-trust/sbom.json", b"sbom")
    scan_digest, _ = _write(root, "release-trust/vulnerability-scan.json", b"scan")
    provenance_digest, _ = _write(
        root, "release-trust/build-provenance.json", b"provenance"
    )
    signature_limitation = (
        "No independently authenticated release signature is configured."
    )
    bundle = ReleaseTrustBundle(
        schema_version="1",
        source=SourceIdentity(
            distribution="statewake-ai",
            version="0.4.1",
            source_revision="tree:fixture",
            source_tree_sha256="a" * 64,
            dependency_lock_sha256="b" * 64,
        ),
        artifacts=(
            ArtifactDigest(
                name="statewake_ai-0.4.1-py3-none-any.whl",
                sha256=wheel_digest,
                size_bytes=wheel_size,
                media_type="application/zip",
            ),
        ),
        build=BuildProvenance(
            builder="uv_build",
            build_type="wheel",
            build_steps=("uv build",),
            environment={"python": "3.13", "platform": "test"},
        ),
        tests=(
            ExternalEvidence(
                evidence_type="tests",
                name="tests.json",
                digest=tests_digest,
                status="passed",
                reference="release-trust/tests.json",
            ),
        ),
        sbom=ExternalEvidence(
            evidence_type="sbom",
            name="sbom.json",
            digest=sbom_digest,
            status="present",
            reference="release-trust/sbom.json",
        ),
        vulnerability_scan=ExternalEvidence(
            evidence_type="vulnerability-scan",
            name="vulnerability-scan.json",
            digest=scan_digest,
            status="passed",
            reference="release-trust/vulnerability-scan.json",
        ),
        signature=ExternalEvidence(
            evidence_type="signature",
            name="signature.json",
            digest="c" * 64,
            status="limitation",
            limitation=signature_limitation,
        ),
        provenance=ExternalEvidence(
            evidence_type="build-provenance",
            name="build-provenance.json",
            digest=provenance_digest,
            status="present",
            reference="release-trust/build-provenance.json",
        ),
        human_decision=HumanReleaseDecision(
            actor_ref="release-owner",
            role="release approver",
            decision="pending",
        ),
        limitations=(signature_limitation,),
    )
    bundle_path = tmp_path / "release-trust.json"
    write_release_trust_bundle(bundle, bundle_path)
    return bundle_path, root, bundle


def _workspace_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    workspace = StateWakeWorkspace.open(root)
    record = workspace.ingest(
        b"workspace-record",
        producer_type="fixture",
        producer_id="producer-1",
        source_ref="fixture-source",
        captured_at=datetime(2026, 9, 29, tzinfo=UTC),
        source_event_id="event-1",
        run_id="run-1",
    )
    workspace.repository.upsert_retention(
        object_id=record.record_id,
        policy_id="retain-30d",
        sensitivity="internal",
        retain_until="2026-10-29T00:00:00+00:00",
        legal_hold=True,
    )
    workspace.repository.record_export(
        export_id="export-1",
        format_record="json",
        created_at="2026-09-29T00:00:00+00:00",
        query_definition_json='{"secret_query":"must-not-leak"}',
        disclosure_max_sensitivity="internal",
        source_schema_version="1",
        output_path=str(tmp_path / "private" / "absolute" / "export.json"),
        output_digest="d" * 64,
        row_count=1,
    )
    workspace.close()
    return root


def test_release_trust_endpoint_separates_content_signature_and_human_authority(
    tmp_path: Path,
) -> None:
    bundle_path, release_root, bundle = _release_fixture(tmp_path)
    workspace_root = _workspace_fixture(tmp_path)
    app = create_read_application(
        ReadApiConfig(
            workspace_root,
            release_bundle_path=bundle_path,
            release_root=release_root,
        )
    )
    status, headers, payload = _request(app, "/api/v1/release-trust")
    assert status == "200 OK"
    assert headers["ETag"]
    assert payload["bundle_digest"] == bundle.digest
    content_verification = cast(dict[str, object], payload["content_verification"])
    assert content_verification["complete"] is True
    signature_authenticity = cast(dict[str, object], payload["signature_authenticity"])
    assert signature_authenticity["authenticated"] is None
    human_decision = cast(dict[str, object], payload["human_decision"])
    assert human_decision["decision"] == "pending"
    assert payload["publication_authorized"] is False
    assert payload["release_published"] is False
    registry = cast(dict[str, object], payload["registry_publication"])
    assert registry["configured"] is False
    assert registry["registry_reconciled"] is False


def test_release_trust_endpoint_projects_active_and_revoked_publication_authority(
    tmp_path: Path,
) -> None:
    bundle_path, release_root, bundle = _release_fixture(tmp_path)
    workspace_root = _workspace_fixture(tmp_path)
    basis = publication_basis_from_release_trust(bundle, target_repository="pypi")
    basis_path = tmp_path / "publication-basis.json"
    write_release_publication_basis(basis, basis_path)
    approval_workspace = tmp_path / "publication-authority"
    store = WorkspaceHumanApprovalStore(approval_workspace)
    approval, created = record_publication_authorization(
        store,
        basis,
        actor_identity_ref="release-owner",
        actor_role="release approver",
        producer_id="github-actions:example/statewake",
        run_id="github-run:1:1",
        reason="protected publication approval",
        idempotency_key="publication:pypi:1:1",
    )
    assert created is True

    config = ReadApiConfig(
        workspace_root,
        release_bundle_path=bundle_path,
        release_root=release_root,
        publication_basis_path=basis_path,
        publication_approval_workspace=approval_workspace,
        publication_expected_producer_id="github-actions:example/statewake",
    )
    app = create_read_application(config)
    status, _, payload = _request(app, "/api/v1/release-trust")
    assert status == "200 OK"
    assert payload["publication_authorized"] is True
    projected = cast(dict[str, object], payload["publication_authorization"])
    assert projected["configured"] is True
    assert projected["active_approval_receipt_ids"] == [approval.receipt.receipt_id]

    revocation, revoked = revoke_publication_authorization(
        store,
        basis,
        target_approval_receipt_id=approval.receipt.receipt_id,
        actor_identity_ref="release-owner",
        actor_role="release approver",
        producer_id="github-actions:example/statewake",
        run_id="github-run:2:1",
        reason="release withdrawn",
        idempotency_key="publication:pypi:2:1:revoke",
    )
    assert revoked is True
    assert revocation.receipt.receipt_id
    status, _, payload = _request(
        create_read_application(config), "/api/v1/release-trust"
    )
    assert status == "200 OK"
    assert payload["publication_authorized"] is False
    projected = cast(dict[str, object], payload["publication_authorization"])
    assert projected["active_approval_receipt_ids"] == []
    items = cast(list[dict[str, object]], projected["items"])
    assert items[0]["status"] == "revoked"


def test_release_trust_endpoint_projects_reconciled_registry_publication(
    tmp_path: Path,
) -> None:
    bundle_path, release_root, bundle = _release_fixture(tmp_path)
    workspace_root = _workspace_fixture(tmp_path)
    basis = publication_basis_from_release_trust(bundle, target_repository="pypi")
    basis_path = tmp_path / "publication-basis.json"
    write_release_publication_basis(basis, basis_path)
    approval_workspace = tmp_path / "publication-authority"
    store = WorkspaceHumanApprovalStore(approval_workspace)
    approval, created = record_publication_authorization(
        store,
        basis,
        actor_identity_ref="release-owner",
        actor_role="release approver",
        producer_id="github-actions:example/statewake",
        run_id="github-run:1:1",
        reason="protected publication approval",
        idempotency_key="publication:pypi:1:1",
    )
    assert created is True
    permit = PublicationExecutionPermit(
        basis_digest=basis.digest,
        target_repository="pypi",
        source_revision=basis.source_revision,
        artifact_sha256=tuple((item.name, item.sha256) for item in basis.artifacts),
        authorization_receipt_ids=(approval.receipt.receipt_id,),
        authorization_receipt_digests=(approval.receipt.digest,),
        issued_at=datetime(2026, 10, 4, 12, 0, tzinfo=UTC),
    )
    permit_path = tmp_path / "publication-permit.json"
    write_publication_execution_permit(permit, permit_path)
    receipt = RegistryPublicationReceipt(
        basis_digest=basis.digest,
        permit_digest=permit.digest,
        target_repository="pypi",
        distribution=basis.distribution,
        version=basis.version,
        registry_api_url="https://pypi.org/pypi/statewake-ai/0.4.1/json",
        observed_at=datetime(2026, 10, 4, 12, 2, tzinfo=UTC),
        artifacts=tuple(
            RegistryPublishedArtifact(
                name=item.name,
                sha256=item.sha256,
                size_bytes=item.size_bytes,
                url=f"https://files.pythonhosted.org/packages/{item.name}",
                package_type="bdist_wheel",
                upload_time=datetime(2026, 10, 4, 12, 1, tzinfo=UTC),
                yanked=False,
            )
            for item in basis.artifacts
        ),
    )
    receipt_path = tmp_path / "registry-publication-receipt.json"
    write_registry_publication_receipt(receipt, receipt_path)

    app = create_read_application(
        ReadApiConfig(
            workspace_root,
            release_bundle_path=bundle_path,
            release_root=release_root,
            publication_basis_path=basis_path,
            publication_approval_workspace=approval_workspace,
            publication_expected_producer_id="github-actions:example/statewake",
            publication_permit_path=permit_path,
            publication_registry_receipt_path=receipt_path,
        )
    )
    status, _, payload = _request(app, "/api/v1/release-trust")
    assert status == "200 OK"
    assert payload["publication_authorized"] is True
    assert payload["release_published"] is True
    projected = cast(dict[str, object], payload["registry_publication"])
    assert projected["configured"] is True
    assert projected["registry_reconciled"] is True
    assert projected["public_bytes_verified"] is True
    assert projected["receipt_digest"] == receipt.digest

    lifecycle_path = tmp_path / "registry-publication-lifecycle.jsonl"
    observation = reconcile_registry_publication_lifecycle(
        receipt,
        basis,
        permit,
        None,
        {},
        unavailable_reason="release-specific registry API returned HTTP 404",
        observed_at=receipt.observed_at + timedelta(minutes=1),
    )
    lifecycle_store = RegistryPublicationLifecycleStore(lifecycle_path)
    assert lifecycle_store.append(observation, receipt, basis, permit) is True
    app = create_read_application(
        ReadApiConfig(
            workspace_root,
            release_bundle_path=bundle_path,
            release_root=release_root,
            publication_basis_path=basis_path,
            publication_approval_workspace=approval_workspace,
            publication_expected_producer_id="github-actions:example/statewake",
            publication_permit_path=permit_path,
            publication_registry_receipt_path=receipt_path,
            publication_registry_lifecycle_path=lifecycle_path,
        )
    )
    status, _, payload = _request(app, "/api/v1/release-trust")
    assert status == "200 OK"
    projected = cast(dict[str, object], payload["registry_publication"])
    lifecycle = cast(dict[str, object], projected["lifecycle"])
    assert lifecycle["configured"] is True
    assert lifecycle["current_status"] == "unavailable"
    assert lifecycle["registry_entry_present"] is False
    assert lifecycle["default_install_eligible"] is False
    assert lifecycle["public_bytes_verified"] is False


def test_validation_study_endpoint_preserves_fixture_scope_and_denominators(
    tmp_path: Path,
) -> None:
    workspace_root = _workspace_fixture(tmp_path)
    study = run_comparative_validation_study()
    study_path = tmp_path / "study.json"
    study_path.write_text(render_study_json(study), encoding="utf-8")
    app = create_read_application(
        ReadApiConfig(workspace_root, validation_study_path=study_path)
    )
    status, _, payload = _request(app, "/api/v1/validation-study")
    assert status == "200 OK"
    assert payload["study_kind"] == "deterministic-fixture-study"
    assert payload["study_digest"] == study.digest
    metrics = cast(list[dict[str, object]], payload["metrics"])
    first = metrics[0]
    assert first["fault_detection_denominator"] == first["injected_fault_count"]
    limitations = cast(list[str], payload["limitations"])
    assert any("fixtures" in item.lower() for item in limitations)


def test_validation_study_rejects_inconsistent_denominator(tmp_path: Path) -> None:
    workspace_root = _workspace_fixture(tmp_path)
    study = run_comparative_validation_study()
    payload = json.loads(render_study_json(study))
    payload["metrics"][0]["case_count"] += 1
    unsigned = {key: value for key, value in payload.items() if key != "digest"}
    payload["digest"] = canonical_digest(unsigned)
    study_path = tmp_path / "study.json"
    study_path.write_text(json.dumps(payload), encoding="utf-8")
    app = create_read_application(
        ReadApiConfig(workspace_root, validation_study_path=study_path)
    )
    status, _, body = _request(app, "/api/v1/validation-study")
    assert status == "422 Unprocessable Entity"
    error = cast(dict[str, object], body["error"])
    assert error["code"] == "INVALID_OPERATIONAL_SOURCE"


def test_validation_study_requires_digest_and_strict_scalar_types(
    tmp_path: Path,
) -> None:
    workspace_root = _workspace_fixture(tmp_path)
    study = run_comparative_validation_study()
    missing_digest = json.loads(render_study_json(study))
    missing_digest.pop("digest")
    study_path = tmp_path / "study.json"
    study_path.write_text(json.dumps(missing_digest), encoding="utf-8")
    app = create_read_application(
        ReadApiConfig(workspace_root, validation_study_path=study_path)
    )
    status, _, body = _request(app, "/api/v1/validation-study")
    assert status == "422 Unprocessable Entity"
    error = cast(dict[str, object], body["error"])
    assert error["code"] == "INVALID_OPERATIONAL_SOURCE"

    malformed = json.loads(render_study_json(study))
    malformed["cases"][0]["false_positive"] = "false"
    unsigned = {key: value for key, value in malformed.items() if key != "digest"}
    malformed["digest"] = canonical_digest(unsigned)
    study_path.write_text(json.dumps(malformed), encoding="utf-8")
    status, _, body = _request(app, "/api/v1/validation-study")
    assert status == "422 Unprocessable Entity"
    error = cast(dict[str, object], body["error"])
    assert error["code"] == "INVALID_OPERATIONAL_SOURCE"


def test_workspace_operations_is_bounded_read_only_and_secret_safe(
    tmp_path: Path,
) -> None:
    workspace_root = _workspace_fixture(tmp_path)
    before = {
        path.relative_to(workspace_root).as_posix(): (
            path.stat().st_size,
            path.stat().st_mtime_ns,
        )
        for path in workspace_root.rglob("*")
        if path.is_file()
    }
    app = create_read_application(ReadApiConfig(workspace_root))
    status, _, payload = _request(
        app, "/api/v1/workspace/operations", "limit=1&offset=0"
    )
    assert status == "200 OK"
    workspace = cast(dict[str, object], payload["workspace"])
    assert workspace["mode"] == "read-only"
    storage = cast(dict[str, object], payload["storage"])
    assert cast(int, storage["database_bytes"]) > 0
    records = cast(dict[str, object], payload["records"])
    assert records["limit"] == 1
    lifecycle = cast(dict[str, object], payload["lifecycle"])
    assert lifecycle["legal_holds_in_page"] == 1
    exports = cast(dict[str, object], payload["exports"])
    export_items = cast(list[dict[str, object]], exports["items"])
    export = export_items[0]
    assert "output_path" not in export
    assert "query_definition_json" not in export
    backup = cast(dict[str, object], payload["backup"])
    assert backup["history_status"] == "not_recorded"
    serialized = json.dumps(payload)
    assert str(tmp_path) not in serialized
    assert "must-not-leak" not in serialized
    after = {
        path.relative_to(workspace_root).as_posix(): (
            path.stat().st_size,
            path.stat().st_mtime_ns,
        )
        for path in workspace_root.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_workspace_operations_rejects_unbounded_query_parameters(
    tmp_path: Path,
) -> None:
    app = create_read_application(ReadApiConfig(_workspace_fixture(tmp_path)))
    status, _, payload = _request(app, "/api/v1/workspace/operations", "limit=10000")
    assert status == "400 Bad Request"
    error = cast(dict[str, object], payload["error"])
    assert error["code"] == "INVALID_WORKSPACE_QUERY"


def test_workspace_operations_rejects_duplicate_query_parameters(
    tmp_path: Path,
) -> None:
    app = create_read_application(ReadApiConfig(_workspace_fixture(tmp_path)))
    status, _, payload = _request(
        app, "/api/v1/workspace/operations", "limit=1&limit=2"
    )
    assert status == "400 Bad Request"
    error = cast(dict[str, object], payload["error"])
    assert error["code"] == "INVALID_WORKSPACE_QUERY"


def test_operational_sources_enforce_specific_size_boundary(tmp_path: Path) -> None:
    """Oversized configured artifacts must fail as bounded operational inputs."""
    bundle_path, _, _ = _release_fixture(tmp_path)
    workspace_root = _workspace_fixture(tmp_path)
    app = create_read_application(
        ReadApiConfig(
            workspace_root,
            release_bundle_path=bundle_path,
            max_release_bundle_bytes=1,
        )
    )
    status, _, payload = _request(app, "/api/v1/release-trust")
    assert status == "413 Request Entity Too Large"
    error = cast(dict[str, object], payload["error"])
    assert error["code"] == "OPERATIONAL_SOURCE_TOO_LARGE"


def test_workspace_corruption_is_bounded_as_unavailable(tmp_path: Path) -> None:
    """Repository corruption must not escape the read API as an internal exception."""
    workspace_root = _workspace_fixture(tmp_path)
    database = workspace_root / "statewake.db"
    database.write_bytes(b"not-a-sqlite-database")
    app = create_read_application(ReadApiConfig(workspace_root))
    status, _, payload = _request(app, "/api/v1/workspace/operations")
    assert status == "503 Service Unavailable"
    error = cast(dict[str, object], payload["error"])
    assert error["code"] == "WORKSPACE_UNAVAILABLE"


def test_operational_routes_honor_etag_conditional_reads(tmp_path: Path) -> None:
    bundle_path, release_root, _ = _release_fixture(tmp_path)
    study = run_comparative_validation_study()
    study_path = tmp_path / "study.json"
    study_path.write_text(render_study_json(study), encoding="utf-8")
    app = create_read_application(
        ReadApiConfig(
            _workspace_fixture(tmp_path),
            release_bundle_path=bundle_path,
            release_root=release_root,
            validation_study_path=study_path,
        )
    )
    for path in (
        "/api/v1/release-trust",
        "/api/v1/validation-study",
        "/api/v1/workspace/operations",
    ):
        status, headers, _ = _request(app, path)
        assert status == "200 OK"
        etag = headers["ETag"]
        cached_status, cached_headers, cached_payload = _request(
            app, path, if_none_match=etag
        )
        assert cached_status == "304 Not Modified"
        assert cached_headers["ETag"] == etag
        assert cached_payload == {}


def test_capabilities_advertise_only_configured_optional_operational_sources(
    tmp_path: Path,
) -> None:
    bundle_path, _, _ = _release_fixture(tmp_path)
    study = run_comparative_validation_study()
    study_path = tmp_path / "study.json"
    study_path.write_text(render_study_json(study), encoding="utf-8")
    app = create_read_application(
        ReadApiConfig(
            _workspace_fixture(tmp_path),
            release_bundle_path=bundle_path,
            validation_study_path=study_path,
        )
    )
    status, _, payload = _request(app, "/api/v1/capabilities")
    assert status == "200 OK"
    features = cast(dict[str, object], payload["features"])
    assert features["release_trust_read"] is True
    assert features["validation_study_read"] is True
    assert features["workspace_operations_read"] is True
