"""Shared execution helpers for the three StateWake golden applications."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from statewake import IntegrationContext, StateWakeClient

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[3]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from scripts.testing.run_real_world_scenarios import (  # noqa: E402
    SCENARIOS,
    Scenario,
    run_scenario,
)
from statewake.sdk import (  # noqa: E402
    AgentEvidenceAdapter,
    AgentRunEvidence,
    IdentityConflictError,
    WebhookEvent,
    WebhookEvidenceAdapter,
)


@dataclass(frozen=True, slots=True)
class GoldenResult:
    """Summarize a golden application execution."""

    application: str
    scenario_id: str
    evidence_receipt_id: str
    chain_verified: bool
    outcome_verified: bool
    proof_bundle_verified: bool
    tamper_rejected: bool
    injected_failure: str


def scenario(scenario_id: str) -> Scenario:
    """Return one canonical scenario from the existing scenario matrix."""
    return next(item for item in SCENARIOS if item.scenario_id == scenario_id)


def run_payment() -> GoldenResult:
    """Run the payment producer, webhook adapter, and reliability lifecycle."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        client = StateWakeClient.for_root(
            IntegrationContext("golden-payment-gateway", run_id="payment-run"),
            root=root / "sdk",
        )
        event = WebhookEvent(
            request_id="evt_payment_001",
            body=json.dumps(
                {"event": "payment_intent.succeeded", "payment_id": "pi_demo_001"},
                sort_keys=True,
            ).encode("utf-8"),
            content_type="application/json",
            signature="synthetic-signature",
            delivery_attempt=1,
        )
        adapter = WebhookEvidenceAdapter(client)
        captured_at = datetime.now(UTC)
        receipt = adapter.ingest(event, captured_at=captured_at)
        adapter.ingest(event, captured_at=captured_at)
        try:
            adapter.ingest(
                WebhookEvent(
                    event.request_id,
                    b'{"event":"payment_intent.failed"}',
                    event.content_type,
                ),
                captured_at=captured_at,
            )
        except IdentityConflictError:
            failure = "same webhook identity with different bytes was rejected"
        else:
            raise AssertionError("payment identity conflict was not rejected")
        result = run_scenario(scenario("payment-gateway"))
        return GoldenResult(
            "payment-reliability",
            "payment-gateway",
            receipt.receipt_id,
            bool(result["chain_verified"]),
            bool(result["outcome_verified"]),
            bool(result["proof_bundle_verified"]),
            bool(result["tamper_rejected"]),
            failure,
        )


def run_enterprise_ai() -> GoldenResult:
    """Run the AI producer, reference-only agent adapter, and reliability lifecycle."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        client = StateWakeClient.for_root(
            IntegrationContext("golden-enterprise-ai", run_id="ai-run"),
            root=root / "sdk",
        )
        evidence = AgentRunEvidence(
            run_id="ai-run",
            model_id="enterprise-model@2026.09",
            prompt_ref="sha256:prompt-demo-001",
            retrieval_ref="sha256:retrieval-policy-v5",
            tool_call_ref="sha256:policy-search",
            tool_result_ref="sha256:source-resolver-result",
            output_ref="sha256:answer-demo-001",
            evaluator_ref="sha256:evaluator-demo-001",
        )
        receipt = AgentEvidenceAdapter(client).ingest(
            evidence, captured_at=datetime.now(UTC)
        )
        result = run_scenario(scenario("enterprise-rag"))
        return GoldenResult(
            "enterprise-ai-reliability",
            "enterprise-rag",
            receipt.receipt_id,
            bool(result["chain_verified"]),
            bool(result["outcome_verified"]),
            bool(result["proof_bundle_verified"]),
            bool(result["tamper_rejected"]),
            "stale retrieval is represented by the existing behavioral-evidence path",
        )


def run_municipal() -> GoldenResult:
    """Run the municipal producer and reliability lifecycle with a review outcome."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        client = StateWakeClient.for_root(
            IntegrationContext("golden-municipal-service", run_id="municipal-run"),
            root=root / "sdk",
        )
        payload = {
            "request_id": "311-DEMO-001",
            "classification": "street-condition",
            "priority": "high",
            "policy_version": "rules-v3",
            "routing": "public-works",
        }
        receipt = client.ingest_bytes(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8"),
            producer_type="municipal-service",
            source_ref="311-DEMO-001",
            source_event_id="311-DEMO-001",
            captured_at=datetime.now(UTC),
        )
        result = run_scenario(scenario("municipal-311"))
        return GoldenResult(
            "municipal-decision-reliability",
            "municipal-311",
            receipt.receipt_id,
            bool(result["chain_verified"]),
            bool(result["outcome_verified"]),
            bool(result["proof_bundle_verified"]),
            bool(result["tamper_rejected"]),
            "policy-version change produces a degraded/review reliability outcome",
        )


def print_result(result: GoldenResult) -> None:
    """Print a compact, machine-readable golden-application result."""
    print(json.dumps(asdict(result), sort_keys=True, indent=2))
