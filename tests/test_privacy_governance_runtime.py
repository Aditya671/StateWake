"""End-to-end runtime privacy and evidence-governance regression coverage."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from statewake.adapters.content_store import ContentAddressedArtifactStore
from statewake.adapters.evidence_ingestion import (
    JsonEvidenceReceiptStore,
    LocalEvidenceIngestionAdapter,
)
from statewake.adapters.opentelemetry import OpenTelemetryTelemetrySink
from statewake.domain.events import EventEnvelope
from statewake.domain.evidence import EvidenceItem, EvidenceManifest
from statewake.domain.governance import (
    EvidenceGovernancePolicy,
    PrivacyGovernanceRuntimeConfig,
)
from statewake.domain.privacy import PrivacyPolicy, RedactionRule
from statewake.services.privacy_governance_runtime_service import (
    load_privacy_governance_runtime_snapshot,
    runtime_config_digest,
)
from statewake.utils.json_support import JsonObject
from statewake.workspace import StateWakeWorkspace
from statewake.workspace.models import WorkspaceRecordQuery


class _Span:
    """Minimal OpenTelemetry span test double."""

    def __init__(self, attributes: dict[str, str]) -> None:
        self.attributes = dict(attributes)
        self.events: list[tuple[str, dict[str, str]]] = []

    def add_event(
        self, name: str, *, attributes: dict[str, str], timestamp: int
    ) -> None:
        del timestamp
        self.events.append((name, dict(attributes)))

    def set_status(self, value: object) -> None:
        del value

    def end(self, *, end_time: int | None = None) -> None:
        del end_time


class _Tracer:
    """Minimal OpenTelemetry tracer test double."""

    def __init__(self) -> None:
        self.spans: list[_Span] = []

    def start_span(
        self, name: str, *, attributes: dict[str, str], start_time: int
    ) -> _Span:
        del name, start_time
        span = _Span(attributes)
        self.spans.append(span)
        return span


def _runtime(*, storage_max: str = "restricted") -> PrivacyGovernanceRuntimeConfig:
    return PrivacyGovernanceRuntimeConfig(
        privacy_policy=PrivacyPolicy(
            policy_id="privacy-1",
            rules=(RedactionRule("email", r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"),),
        ),
        evidence_policy=EvidenceGovernancePolicy(
            policy_id="evidence-1",
            storage_max_sensitivity=storage_max,
            telemetry_max_sensitivity="internal",
            require_digest_for=("restricted",),
        ),
    )


def test_governed_ingestion_redacts_before_receipt_identity(tmp_path: Path) -> None:
    adapter = LocalEvidenceIngestionAdapter(
        ContentAddressedArtifactStore(tmp_path / "artifacts"),
        JsonEvidenceReceiptStore(tmp_path / "receipts"),
        privacy_governance=_runtime(),
    )
    receipt = adapter.ingest_bytes(
        b"opaque artifact bytes",
        producer_type="test",
        producer_id="producer",
        source_ref="source",
        captured_at=datetime(2026, 9, 30, tzinfo=UTC),
        metadata={"authorization": "Bearer secret", "message": "alice@example.com"},
        sensitivity="confidential",
    )
    assert receipt.metadata == {
        "authorization": "[REDACTED]",
        "message": "[REDACTED]",
    }
    persisted = json.loads(
        (tmp_path / "receipts" / f"{receipt.receipt_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert "Bearer secret" not in json.dumps(persisted)
    assert "alice@example.com" not in json.dumps(persisted)


def test_governance_rejects_before_artifact_or_receipt_write(tmp_path: Path) -> None:
    adapter = LocalEvidenceIngestionAdapter(
        ContentAddressedArtifactStore(tmp_path / "artifacts"),
        JsonEvidenceReceiptStore(tmp_path / "receipts"),
        privacy_governance=_runtime(storage_max="confidential"),
    )
    with pytest.raises(ValueError, match="storage rejected by governance policy"):
        adapter.ingest_bytes(
            b"must not be written",
            producer_type="test",
            producer_id="producer",
            source_ref="source",
            captured_at=datetime(2026, 9, 30, tzinfo=UTC),
            sensitivity="restricted",
        )
    assert not list((tmp_path / "artifacts").rglob("*"))
    assert not list((tmp_path / "receipts").rglob("*"))


def test_workspace_indexes_governed_sensitivity_and_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    snapshot = tmp_path / "privacy-governance.json"
    runtime = _runtime()
    with StateWakeWorkspace.open(
        root,
        privacy_governance=runtime,
        privacy_governance_snapshot_path=snapshot,
    ) as workspace:
        record = workspace.ingest(
            b"governed",
            producer_type="test",
            producer_id="producer",
            source_ref="source",
            captured_at=datetime(2026, 9, 30, tzinfo=UTC),
            sensitivity="confidential",
        )
        page = workspace.query(
            WorkspaceRecordQuery(record_id=record.record_id, limit=1)
        )
        assert page.records[0].sensitivity == "confidential"
        assert page.records[0].policy_id == "evidence-1"
    loaded = load_privacy_governance_runtime_snapshot(snapshot, max_bytes=256 * 1024)
    assert loaded == runtime
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    assert payload["digest"] == runtime_config_digest(runtime)


def test_runtime_snapshot_rejects_tampering(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    snapshot = tmp_path / "privacy-governance.json"
    with StateWakeWorkspace.open(
        root,
        privacy_governance=_runtime(),
        privacy_governance_snapshot_path=snapshot,
    ):
        pass
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    payload["evidence_governance_policy"]["telemetry_max_sensitivity"] = "restricted"
    snapshot.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="digest mismatch"):
        load_privacy_governance_runtime_snapshot(snapshot, max_bytes=256 * 1024)


def test_telemetry_projection_omits_evidence_above_ceiling() -> None:
    tracer = _Tracer()
    runtime = _runtime()
    manifest = EvidenceManifest(
        "manifest-1",
        "run-1",
        (
            EvidenceItem(
                "internal-1", "source", digest="a" * 64, sensitivity="internal"
            ),
            EvidenceItem(
                "restricted-1", "source", digest="b" * 64, sensitivity="restricted"
            ),
        ),
    )
    sink = OpenTelemetryTelemetrySink(tracer, privacy_governance=runtime)
    sink.emit(
        EventEnvelope(
            "run-1",
            0,
            datetime(2026, 9, 30, tzinfo=UTC),
            "run.started",
            "runtime",
            metadata={"authorization": "secret"},
        ),
        evidence_manifest=manifest,
    )
    attributes = tracer.spans[0].attributes
    assert attributes["statewake.evidence.visible_ids"] == "internal-1"
    assert attributes["statewake.evidence.omitted_count"] == "1"
    assert "restricted-1" not in json.dumps(attributes)
    assert "secret" not in json.dumps(attributes)


def test_runtime_snapshot_rejects_symlink_and_oversize(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    snapshot = tmp_path / "privacy-governance.json"
    with StateWakeWorkspace.open(
        root,
        privacy_governance=_runtime(),
        privacy_governance_snapshot_path=snapshot,
    ):
        pass

    with pytest.raises(OverflowError, match="exceeds read limit"):
        load_privacy_governance_runtime_snapshot(snapshot, max_bytes=8)

    alias = tmp_path / "snapshot-link.json"
    try:
        alias.symlink_to(snapshot)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable in this environment")
    with pytest.raises(ValueError, match="cannot traverse a symlink"):
        load_privacy_governance_runtime_snapshot(alias, max_bytes=256 * 1024)


def test_runtime_snapshot_uses_restrictive_permissions(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    snapshot = tmp_path / "privacy-governance.json"
    with StateWakeWorkspace.open(
        root,
        privacy_governance=_runtime(),
        privacy_governance_snapshot_path=snapshot,
    ):
        pass
    if sys.platform == "win32":
        pytest.skip("POSIX mode bits do not represent Windows ACL permissions")
    assert snapshot.stat().st_mode & 0o777 == 0o600


def test_invalid_sensitivity_rejected_before_any_write(tmp_path: Path) -> None:
    adapter = LocalEvidenceIngestionAdapter(
        ContentAddressedArtifactStore(tmp_path / "artifacts"),
        JsonEvidenceReceiptStore(tmp_path / "receipts"),
        privacy_governance=_runtime(),
    )
    with pytest.raises(ValueError, match="sensitivity must be one of"):
        adapter.ingest_bytes(
            b"must not be written",
            producer_type="test",
            producer_id="producer",
            source_ref="source",
            captured_at=datetime(2026, 9, 30, tzinfo=UTC),
            sensitivity="secret",
        )
    assert not list((tmp_path / "artifacts").rglob("*"))
    assert not list((tmp_path / "receipts").rglob("*"))


def test_contract_capture_persistence_propagates_evidence_sensitivity(
    tmp_path: Path,
) -> None:
    from statewake.integrations.base import ContractCaptureResult

    class _Contract:
        def to_dict(self) -> JsonObject:
            return {}

        def to_evidence_item(self) -> EvidenceItem:
            raise AssertionError("not called by persist")

    captured_at = "2026-09-30T00:00:00+00:00"
    payload: JsonObject = {"captured_at": captured_at, "value": "governed"}
    from statewake.ai_contracts.base import canonical_json_bytes, sha256_hex

    digest = sha256_hex(canonical_json_bytes(payload))
    result = ContractCaptureResult(
        contract=_Contract(),
        payload=payload,
        evidence=EvidenceItem(
            evidence_id="contract-evidence",
            source="integration",
            digest=digest,
            sensitivity="confidential",
            metadata={
                "producer_id": "producer",
                "run_id": "run-1",
                "contract_type": "retrieval",
            },
        ),
    )
    with StateWakeWorkspace.open(
        tmp_path / "workspace",
        privacy_governance=_runtime(),
    ) as workspace:
        record = result.persist(workspace)
        assert record.sensitivity == "confidential"
        assert record.policy_id == "evidence-1"
