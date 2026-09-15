"""Executable integration coverage for representative StateWake host systems."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

import pytest

from scripts.testing.run_real_world_scenarios import SCENARIOS, run_scenario
from statewake.adapters.content_store import ContentAddressedArtifactStore
from statewake.adapters.evidence_ingestion import (
    JsonEvidenceReceiptStore,
    LocalEvidenceIngestionAdapter,
)
from statewake.adapters.reliability_state import JsonlReliabilityStateStore
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.server import VerificationServiceConfig, create_application
from statewake.services.reliability_state_service import transition_reliability_state


def test_all_real_world_scenarios_pass() -> None:
    """Require every documented real-world scenario to pass its full lifecycle."""
    results = [run_scenario(scenario) for scenario in SCENARIOS]
    assert len(results) == 24
    assert all(result["chain_verified"] for result in results)
    assert all(result["outcome_verified"] for result in results)
    assert all(result["proof_bundle_verified"] for result in results)
    assert all(result["tamper_rejected"] for result in results)


def test_recovery_scenario_exercises_full_recovery_path() -> None:
    """Require the supply-chain scenario to prove predecessor failure before recovery."""
    result = run_scenario(
        next(item for item in SCENARIOS if item.scenario_id == "supply-chain")
    )
    assert result["reliability_state"] == "recovered"
    assert result["decision"] == "accept"
    assert result["precursor_verified"] is True
    assert "recovery_outcome_binding" in result["checks"]  # type: ignore


def test_evidence_receipt_is_idempotent_and_conflict_safe() -> None:
    """Require duplicate producer occurrences to be stable
    and conflicting ones to fail."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "event.json"
        source.write_text(
            '{"event":"payment.succeeded","id":"evt-1"}\n', encoding="utf-8"
        )
        adapter = LocalEvidenceIngestionAdapter(
            ContentAddressedArtifactStore(root / "artifacts"),
            JsonEvidenceReceiptStore(root / "receipts"),
        )
        kwargs = {
            "producer_type": "payment-gateway",
            "producer_id": "demo",
            "source_event_id": "evt-1",
            "run_id": "run-1",
            "captured_at": datetime(2026, 9, 12, tzinfo=UTC),
        }
        first = adapter.ingest_file(source, **kwargs)  # type: ignore
        second = adapter.ingest_file(source, **kwargs)  # type: ignore
        assert first.to_dict() == second.to_dict()
        source.write_text('{"event":"payment.failed","id":"evt-1"}\n', encoding="utf-8")
        with pytest.raises(ValueError, match="source_event_id conflict"):
            adapter.ingest_file(source, **kwargs)  # type: ignore


def test_invalid_unknown_to_recovered_transition_is_rejected() -> None:
    """Require recovery to have an actual unreliable predecessor."""
    chain = ReliabilityEvidenceChain(
        chain_id="a" * 64,
        run=EvidenceReference("run", "r", "b" * 64),
        state=EvidenceReference("state", "s", "c" * 64),
        evidence=(EvidenceReference("evidence", "e", "d" * 64),),
        provenance=EvidenceReference("provenance", "p", "e" * 64),
        integrity=EvidenceReference("integrity", "i", "f" * 64),
        verification_status="verified",
        reliability_state="recovered",
        reconciliation_state="recovered",
        decision="accept",
        decision_rationale=("recovery test",),
    )
    with TemporaryDirectory() as directory:
        history = Path(directory) / "history.jsonl"
        with pytest.raises(ValueError, match="invalid reliability-state transition"):
            transition_reliability_state(
                "subject",
                chain,
                store=JsonlReliabilityStateStore(history),
                actor="test",
                occurred_at=datetime(2026, 9, 12, tzinfo=UTC),
            )


def _wsgi_call(
    application: Any,
    *,
    path: str,
    method: str = "GET",
    body: bytes = b"",
    scheme: str = "http",
) -> tuple[str, dict[str, str], bytes]:
    """Call a WSGI application in-process and return the response tuple."""
    status_holder: dict[str, str] = {}
    headers: dict[str, str] = {}

    def start_response(
        status: str,
        response_headers: list[tuple[str, str]],
        _exc_info: Any = None,
    ) -> None:
        """Capture the WSGI status and headers."""
        status_holder["status"] = status
        headers.update(dict(response_headers))

    environ: dict[str, object] = {
        "REQUEST_METHOD": method,
        "PATH_INFO": path,
        "wsgi.url_scheme": scheme,
        "wsgi.input": BytesIO(body),
        "CONTENT_LENGTH": str(len(body)),
    }
    response = b"".join(application(cast(Any, environ), start_response))
    return status_holder["status"], headers, response


def test_http_boundary_fails_closed_before_verification_root_access() -> None:
    """Require health and secure verification behavior at the HTTP boundary."""
    with TemporaryDirectory() as directory:
        config = VerificationServiceConfig(artifact_roots=(Path(directory),))
        application = create_application(config)
        status, headers, body = _wsgi_call(application, path="/health")
        assert status == "200 OK"
        assert headers["Content-Type"] == "application/json"
        assert json.loads(body)["status"] == "ok"

        request = json.dumps(
            {"chain_path": "chain.json", "evidence_root": directory}
        ).encode("utf-8")
        status, _, body = _wsgi_call(
            application,
            path="/v1/evidence/verify",
            method="POST",
            body=request,
        )
        payload = json.loads(body)
        assert status == "400 Bad Request"
        assert payload["error"]["code"] == "HTTPS_REQUIRED"
