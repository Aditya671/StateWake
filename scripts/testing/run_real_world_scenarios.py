"""Run credential-free real-world StateWake integration scenarios."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Final

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from config.project_paths import PROJECT_ROOT, SRC_PATH  # noqa: E402

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from statewake.adapters.content_store import ContentAddressedArtifactStore  # noqa: E402
from statewake.adapters.evidence_ingestion import (  # noqa: E402
    JsonEvidenceReceiptStore,
    LocalEvidenceIngestionAdapter,
)
from statewake.adapters.reliability_attestation import (  # noqa: E402
    JsonlReliabilityOutcomeAttestationStore,
)
from statewake.adapters.reliability_state import (  # noqa: E402
    JsonlReliabilityStateStore,  # noqa: E402
)
from statewake.domain.provenance import ProvenanceGraph, ProvenanceNode  # noqa: E402
from statewake.domain.state import SystemState  # noqa: E402
from statewake.services.reliability_attestation_service import (  # noqa: E402
    attest_reliability_outcome,
    write_reliability_outcome_attestation,
)
from statewake.services.reliability_comparison_service import (  # noqa: E402
    build_reliability_behavioral_comparison,
)
from statewake.services.reliability_evidence_service import (  # noqa: E402
    build_reliability_evidence_chain,
    load_reliability_evidence_chain,
    verify_reliability_evidence_chain,
    write_reliability_evidence_chain,
)
from statewake.services.reliability_outcome_verification_service import (  # noqa: E402
    verify_reliability_outcome,
)
from statewake.services.reliability_proof_bundle_service import (  # noqa: E402
    build_reliability_proof_bundle,
    verify_reliability_proof_bundle,
)
from statewake.services.reliability_reconciliation_binding_service import (  # noqa: E402
    build_reliability_reconciliation_binding,
)
from statewake.services.reliability_state_service import (  # noqa: E402
    transition_reliability_state,
)

SCRIPT_ROOT = PROJECT_ROOT
SOURCE_ROOT = SRC_PATH


NOW: Final = datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Scenario:
    """Describe one representative host-system integration scenario."""

    scenario_id: str
    title: str
    producer_type: str
    producer_id: str
    evidence: dict[str, object]
    decision: str
    reliability_state: str
    rationale: tuple[str, ...]
    profile_id: str


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "payment-gateway",
        "Payment gateway authorization",
        "payment-gateway",
        "stripe-like-checkout",
        {
            "event": "payment_intent.succeeded",
            "payment_id": "pi_demo_001",
            "amount": 4999,
            "currency": "usd",
            "merchant": "demo-store",
            "gateway_status": "succeeded",
            "webhook_delivery": 1,
        },
        "accept",
        "reliable",
        ("gateway event receipt matches persisted payment outcome",),
        "release-evidence-complete",
    ),
    Scenario(
        "municipal-311",
        "Municipal 311 prioritization",
        "municipal-311",
        "nyc-311-priority-service",
        {
            "request_id": "311-900001",
            "borough": "Queens",
            "complaint_type": "Street Condition",
            "priority": "high",
            "routing": "DOT",
            "sla_hours": 24,
            "decision_source": "rules-v3",
        },
        "review",
        "degraded",
        (
            "routing rules changed and the behavioral comparison requires operator review",
        ),
        "model-prompt-change-review",
    ),
    Scenario(
        "enterprise-rag",
        "Enterprise RAG answer",
        "enterprise-ai",
        "rag-assistant",
        {
            "request_id": "qa-1001",
            "query": "Which policy governs supplier onboarding?",
            "answer": "Supplier onboarding requires procurement approval and sanctions screening.",
            "retrieval_sources": ["procurement-policy-v5", "supplier-controls-v2"],
            "model": "enterprise-model@2026.09",
            "prompt_digest": "prompt-demo-001",
            "tool_calls": ["policy_search", "source_resolver"],
        },
        "accept",
        "reliable",
        (
            "retrieval sources, prompt state, model state, and answer artifact are bound",
        ),
        "compliance-handoff-ready",
    ),
    Scenario(
        "decision-system",
        "Credit/eligibility decision",
        "decision-engine",
        "eligibility-rules",
        {
            "case_id": "CASE-44001",
            "income": 42000,
            "debt_to_income": 0.62,
            "policy_version": "eligibility-2026.3",
            "decision": "reject",
            "reason_codes": ["DTI_ABOVE_LIMIT"],
        },
        "reject",
        "unreliable",
        ("the authoritative rule outcome rejects the case under the declared policy",),
        "release-evidence-complete",
    ),
    Scenario(
        "supply-chain",
        "Supply-chain ETA recovery",
        "supply-chain",
        "shipment-risk-service",
        {
            "shipment_id": "SHP-7788",
            "carrier": "demo-carrier",
            "baseline_eta": "2026-09-15",
            "observed_eta": "2026-09-19",
            "exception": "port-delay",
            "recovery_action": "reroute-via-alt-port",
        },
        "accept",
        "recovered",
        (
            "observed delay was reconciled and the approved recovery action restored the expected state",
        ),
        "incident-recovery-verified",
    ),
    Scenario(
        "invoice-automation",
        "Invoice-document automation",
        "document-agent",
        "invoice-extraction-agent",
        {
            "document_id": "INV-88001",
            "vendor": "demo-vendor",
            "total": 18500,
            "currency": "usd",
            "po_match": True,
            "human_review": False,
            "extraction_schema": "invoice-v2",
        },
        "accept",
        "reliable",
        (
            "extracted fields and PO match are supported by the document-processing evidence",
        ),
        "compliance-handoff-ready",
    ),
)

GLOBAL_SCENARIOS: Final = (
    Scenario(
        "healthcare-triage",
        "Hospital triage decision",
        "healthcare",
        "triage-service",
        {
            "case_id": "ER-2001",
            "acuity": "high",
            "vitals": "stable",
            "recommended_route": "priority",
            "screening": "verified",
        },
        "accept",
        "reliable",
        ("triage recommendation is bound to verified clinical-routing evidence",),
        "clinical-decision-handoff",
    ),
    Scenario(
        "insurance-claims",
        "Insurance claims adjudication",
        "insurance",
        "claims-engine",
        {
            "claim_id": "CLM-5502",
            "coverage": "active",
            "fraud_flag": "manual-review",
            "policy_version": "claims-2026.4",
        },
        "reject",
        "unreliable",
        ("the claim evidence is insufficient for an automated acceptance decision",),
        "regulated-decision-review",
    ),
    Scenario(
        "fraud-aml",
        "Fraud and AML screening",
        "fraud-aml",
        "screening-engine",
        {
            "case_id": "AML-7008",
            "risk_score": 0.91,
            "sanctions_match": False,
            "pep_match": True,
            "disposition": "manual-review",
        },
        "reject",
        "unreliable",
        ("risk indicators require rejection of automated approval",),
        "regulated-decision-review",
    ),
    Scenario(
        "identity-access",
        "Identity and access authorization",
        "identity",
        "access-policy-engine",
        {
            "request_id": "IAM-901",
            "principal": "service-account-17",
            "resource": "payroll-db",
            "decision": "allow",
            "policy_version": "iam-19",
        },
        "accept",
        "reliable",
        ("identity, resource, policy, and authorization result are bound",),
        "security-authorization",
    ),
    Scenario(
        "utility-outage",
        "Electric utility outage restoration",
        "utility",
        "grid-operations",
        {
            "incident_id": "OUT-4401",
            "region": "Jaipur-West",
            "cause": "feeder-fault",
            "restoration_action": "switch-feeder",
        },
        "accept",
        "recovered",
        (
            "the outage was reconciled and the approved switching action restored service",
        ),
        "incident-recovery-verified",
    ),
    Scenario(
        "telecom-network",
        "Telecom network assurance",
        "telecom",
        "network-assurance",
        {
            "ticket_id": "TEL-8007",
            "site": "cell-221",
            "packet_loss": 0.37,
            "root_cause": "backhaul-degradation",
            "sla_risk": "high",
        },
        "reject",
        "unreliable",
        (
            "observed network conditions violate the declared service reliability threshold",
        ),
        "sla-enforcement",
    ),
    Scenario(
        "industrial-iot",
        "Industrial control anomaly",
        "industrial-iot",
        "plant-monitor",
        {
            "asset_id": "PUMP-42",
            "temperature": 118.2,
            "pressure": 7.8,
            "threshold": 100.0,
            "alarm": "critical",
        },
        "review",
        "degraded",
        ("a sensor-behavior change requires operator review before automated action",),
        "operational-change-review",
    ),
    Scenario(
        "ecommerce-fulfillment",
        "E-commerce fulfillment decision",
        "ecommerce",
        "fulfillment-engine",
        {
            "order_id": "ORD-8802",
            "inventory": 14,
            "reserved": 1,
            "fraud_status": "clear",
            "fulfillment_route": "warehouse-a",
        },
        "accept",
        "reliable",
        ("inventory, reservation, fraud, and fulfillment evidence agree",),
        "fulfillment-handoff",
    ),
    Scenario(
        "legal-compliance",
        "Enterprise legal compliance check",
        "legal-compliance",
        "policy-checker",
        {
            "matter_id": "MAT-310",
            "jurisdiction": "IN",
            "policy_set": "privacy-2026",
            "finding": "exception",
            "owner": "legal",
        },
        "review",
        "degraded",
        (
            "a policy-set change produces a material behavioral difference requiring legal review",
        ),
        "compliance-review",
    ),
    Scenario(
        "payroll-tax",
        "Payroll and tax calculation",
        "payroll-tax",
        "payroll-engine",
        {
            "payroll_id": "PAY-1201",
            "country": "IN",
            "tax_year": 2026,
            "gross": 180000,
            "withholding_status": "verified",
        },
        "accept",
        "reliable",
        ("payroll inputs and the applicable withholding policy are verified",),
        "financial-close-ready",
    ),
    Scenario(
        "autonomous-fleet",
        "Autonomous fleet route decision",
        "autonomous-fleet",
        "fleet-controller",
        {
            "vehicle_id": "AV-17",
            "route_id": "R-991",
            "lidar_health": "degraded",
            "weather": "heavy-rain",
            "safety_mode": "hold",
        },
        "reject",
        "unreliable",
        ("sensor and environmental evidence invalidate the automated route decision",),
        "safety-hold",
    ),
    Scenario(
        "disaster-alerting",
        "Disaster alerting and response",
        "disaster-response",
        "alert-service",
        {
            "event_id": "CYCLONE-27",
            "severity": "extreme",
            "forecast_confidence": 0.96,
            "evacuation_zone": "coastal-zone-3",
            "response_action": "evacuate",
        },
        "accept",
        "recovered",
        (
            "post-event evidence confirms the response state was restored after intervention",
        ),
        "incident-recovery-verified",
    ),
)


WORLD_SCENARIOS: Final = (
    Scenario(
        "financial-markets",
        "Market surveillance decision",
        "financial-markets",
        "market-surveillance",
        {
            "instrument": "XYZ",
            "venue": "demo-exchange",
            "price_move": 0.087,
            "volume_spike": 4.2,
            "surveillance_rule": "market-integrity-v12",
            "disposition": "review",
        },
        "review",
        "degraded",
        ("the surveillance signal changed materially and requires analyst review",),
        "market-integrity-review",
    ),
    Scenario(
        "cybersecurity-soc",
        "SOC incident containment",
        "cybersecurity",
        "soc-orchestrator",
        {
            "incident_id": "INC-2044",
            "severity": "critical",
            "credential_abuse": True,
            "edr_status": "isolated",
            "containment_action": "revoke-session",
            "rule_pack": "soc-2026.9",
        },
        "accept",
        "recovered",
        (
            "the compromised session was contained and post-remediation evidence verified",
        ),
        "security-incident-recovered",
    ),
    Scenario(
        "aviation-operations",
        "Aircraft dispatch safety decision",
        "aviation",
        "dispatch-system",
        {
            "flight": "DEMO-417",
            "airport": "JAI",
            "weather": "crosswind-high",
            "aircraft_status": "serviceable",
            "dispatch_decision": "hold",
            "release_rule": "dispatch-v8",
        },
        "reject",
        "unreliable",
        ("the declared weather constraint invalidates automated dispatch release",),
        "safety-hold",
    ),
    Scenario(
        "education-platform",
        "Student assessment integrity",
        "education",
        "assessment-engine",
        {
            "submission_id": "SUB-441",
            "proctor_signal": "anomalous",
            "identity_match": True,
            "policy_version": "exam-integrity-2026",
            "disposition": "manual-review",
        },
        "review",
        "degraded",
        ("assessment evidence requires human review before final grading",),
        "academic-integrity-review",
    ),
    Scenario(
        "climate-environment",
        "Flood-risk operational alert",
        "climate",
        "flood-forecast-service",
        {
            "basin": "demo-basin",
            "forecast_probability": 0.93,
            "rainfall_mm": 214,
            "gauge_health": "verified",
            "alert_level": "red",
            "response": "evacuate",
        },
        "accept",
        "reliable",
        ("forecast, gauge, threshold, and response evidence agree",),
        "emergency-response-ready",
    ),
    Scenario(
        "emergency-dispatch",
        "Emergency call prioritization",
        "emergency-services",
        "dispatch-priority-engine",
        {
            "call_id": "CALL-9008",
            "reported_condition": "cardiac-arrest",
            "location_verified": True,
            "priority": "life-threatening",
            "dispatch": "advanced-life-support",
        },
        "accept",
        "reliable",
        ("caller, location, triage, and dispatch evidence support the priority",),
        "emergency-dispatch-ready",
    ),
)

SCENARIOS = (  # type: ignore
    SCENARIOS + GLOBAL_SCENARIOS + WORLD_SCENARIOS
)


def _write_json(path: Path, payload: object) -> Path:
    """Write one deterministic JSON artifact."""
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of one artifact."""
    return sha256(path.read_bytes()).hexdigest()


def _prepare_root(
    root: Path, scenario: Scenario
) -> tuple[Path, Path, Path, Path, Path, Path]:
    """Create the common evidence inputs; provenance is finalized later."""
    run = _write_json(root / "run.json", {"run_id": f"run-{scenario.scenario_id}"})
    state = _write_json(
        root / "state.json",
        {
            "state_id": f"state-{scenario.scenario_id}",
            "system": scenario.producer_type,
            "version": "2026.09",
        },
    )
    evidence = _write_json(root / "evidence.json", scenario.evidence)
    provenance = root / "provenance.json"
    integrity = _write_json(
        root / "integrity.json",
        {
            "algorithm": "SHA-256",
            "evidence_digest": _sha256(evidence),
            "verified": True,
        },
    )
    return run, state, evidence, provenance, integrity, root / "chain.json"


def _prepare_receipt(
    root: Path,
    *,
    evidence: Path,
    scenario: Scenario,
    run_id: str,
) -> Path:
    """Exercise the canonical external-evidence receipt boundary."""
    adapter = LocalEvidenceIngestionAdapter(
        artifact_store=ContentAddressedArtifactStore(root / "artifact-store"),
        receipt_store=JsonEvidenceReceiptStore(root / "receipts"),
    )
    receipt = adapter.ingest_file(
        evidence,
        producer_type=scenario.producer_type,
        producer_id=scenario.producer_id,
        source_ref=f"producer://{scenario.producer_id}/{scenario.scenario_id}",
        source_event_id=f"{scenario.scenario_id}-event-1",
        producer_version="2026.09",
        run_id=run_id,
        captured_at=NOW,
        metadata={"scenario": scenario.scenario_id},
    )
    adapter.verify(receipt)
    receipt_path = root / "receipt.json"
    receipt_path.write_text(
        json.dumps(receipt.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return receipt_path


def _write_state(
    path: Path,
    *,
    state_id: str,
    model: str,
    prompt_digest: str,
    policy_digest: str,
) -> Path:
    """Write a canonical StateWake SystemState artifact."""
    state = SystemState(
        state_id=state_id,
        captured_at=NOW,
        agent_version="agent-2026.09",
        model=model,
        prompt_digest=prompt_digest,
        policy_digest=policy_digest,
    )
    return _write_json(path, state.to_dict())


def _write_provenance(
    provenance_path: Path,
    *,
    run: Path,
    state: Path,
    evidence: Path,
    receipt_path: Path,
    extra_paths: tuple[tuple[str, str, Path], ...] = (),
) -> None:
    """Write provenance nodes for all material references in a scenario chain."""
    receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_id = str(receipt_payload["receipt_id"])
    nodes = [
        ProvenanceNode(
            "run",
            "run",
            _sha256(run),
            str(json.loads(run.read_text(encoding="utf-8"))["run_id"]),
            (),
        ),
        ProvenanceNode(
            "state",
            "state",
            _sha256(state),
            json.loads(state.read_text(encoding="utf-8"))["state_id"],
            ("run",),
        ),
        ProvenanceNode("evidence", "evidence", _sha256(evidence), receipt_id, ("run",)),
    ]
    edges = [("state", "run"), ("evidence", "run")]
    parent = "run"
    for node_id, identity, path in extra_paths:
        nodes.append(
            ProvenanceNode(
                node_id, node_id.split("-")[0], _sha256(path), identity, (parent,)
            )
        )
        edges.append((node_id, parent))
        parent = node_id
    graph = ProvenanceGraph(tuple(nodes), tuple(edges))
    _write_json(provenance_path, graph.to_dict())


def _build_chain(
    root: Path,
    scenario: Scenario,
    *,
    run: Path,
    state: Path,
    evidence: Path,
    provenance: Path,
    integrity: Path,
    chain_path: Path,
    receipt_path: Path,
) -> object:
    """Build and seal a scenario-specific evidence chain."""
    run_id = f"run-{scenario.scenario_id}"
    extra_paths: list[tuple[str, str, Path]] = []
    comparison_path: Path | None = None
    reconciliation_path: Path | None = None
    reconciliation_binding_path: Path | None = None
    recovery_path: Path | None = None

    if scenario.reliability_state == "degraded":
        before = _write_state(
            root / "before-state.json",
            state_id="before",
            model="decision-engine@v2",
            prompt_digest="prompt-v2",
            policy_digest="policy-v2",
        )
        after = _write_state(
            root / "after-state.json",
            state_id="after",
            model="decision-engine@v3",
            prompt_digest="prompt-v3",
            policy_digest="policy-v3",
        )
        comparison_path = root / "comparison.json"
        comparison = build_reliability_behavioral_comparison(
            before_state_path=before,
            after_state_path=after,
            output=comparison_path,
        )
        reconciliation_path = _write_json(
            root / "reconciliation.json",
            {
                "reconciliation_id": f"rec-{scenario.scenario_id}",
                "status": "verified",
                "comparison_id": comparison.comparison_id,
                "action": "operator-review-required",
            },
        )
        reconciliation_binding_path = root / "reconciliation-binding.json"
        build_reliability_reconciliation_binding(
            comparison_path=comparison_path,
            reconciliation_path=reconciliation_path,
            output=reconciliation_binding_path,
        )
        extra_paths.extend(
            (
                ("before-state", "before", before),
                ("after-state", "after", after),
                ("comparison", comparison.comparison_id, comparison_path),
                ("reconciliation", f"rec-{scenario.scenario_id}", reconciliation_path),
            )
        )

    if scenario.reliability_state == "recovered":
        before = _write_state(
            root / "before-state.json",
            state_id="before",
            model="shipment-risk@v1",
            prompt_digest="prompt-v1",
            policy_digest="route-v1",
        )
        after = _write_state(
            root / "after-state.json",
            state_id="after",
            model="shipment-risk@v1",
            prompt_digest="prompt-v1",
            policy_digest="route-v2",
        )
        comparison_path = root / "comparison.json"
        comparison = build_reliability_behavioral_comparison(
            before_state_path=before,
            after_state_path=after,
            output=comparison_path,
        )
        recovery_action = str(
            scenario.evidence.get(
                "recovery_action",
                scenario.evidence.get(
                    "restoration_action",
                    scenario.evidence.get("response_action", "restore-service"),
                ),
            )
        )
        reconciliation_path = _write_json(
            root / "reconciliation.json",
            {
                "reconciliation_id": f"rec-{scenario.scenario_id}",
                "status": "recovered",
                "action": recovery_action,
            },
        )
        reconciliation_binding_path = root / "reconciliation-binding.json"
        build_reliability_reconciliation_binding(
            comparison_path=comparison_path,
            reconciliation_path=reconciliation_path,
            output=reconciliation_binding_path,
        )
        recovery_path = _write_json(
            root / "recovery.json",
            {
                "recovery_id": f"recovery-{scenario.scenario_id}",
                "occurred_at": NOW.isoformat(),
                "impact_id": f"impact-{scenario.scenario_id}",
                "source_reconciliation_id": f"rec-{scenario.scenario_id}",
                "actor": "operations",
                "approved": True,
                "status": "applied",
                "steps": [
                    {
                        "step_id": "reroute",
                        "target": "shipment",
                        "action": recovery_action,
                        "status": "applied",
                        "reason": "port-delay",
                    }
                ],
                "reason": "restore committed delivery path",
            },
        )
        extra_paths.extend(
            (
                ("before-state", "before", before),
                ("after-state", "after", after),
                ("comparison", comparison.comparison_id, comparison_path),
                ("reconciliation", f"rec-{scenario.scenario_id}", reconciliation_path),
                ("recovery", f"recovery-{scenario.scenario_id}", recovery_path),
            )
        )

    # Comparison inputs are material lineage references, so give every such artifact a node.
    _write_provenance(
        provenance,
        run=run,
        state=state,
        evidence=evidence,
        receipt_path=receipt_path,
        extra_paths=tuple(extra_paths),
    )

    chain = build_reliability_evidence_chain(
        run_id=run_id,
        run_path=run,
        state_id=f"state-{scenario.scenario_id}",
        state_path=state,
        evidence_paths=(evidence,),
        provenance_path=provenance,
        integrity_proof_path=integrity,
        evidence_receipt_paths={evidence.name: receipt_path},
        verification_status="verified",
        reliability_state=scenario.reliability_state,
        reconciliation_state=(
            "recovered" if scenario.reliability_state == "recovered" else "verified"
        ),
        reconciliation_path=reconciliation_path,
        recovery_path=recovery_path,
        comparison_path=comparison_path,
        reconciliation_binding_path=reconciliation_binding_path,
        decision=scenario.decision,
        rationale=scenario.rationale,
    )
    write_reliability_evidence_chain(chain, chain_path)
    return chain


def _execute_outcome(
    *,
    root: Path,
    chain_path: Path,
    subject_id: str,
    history: Path,
    now: datetime,
) -> tuple[Any, Any, Any]:
    """Persist a state transition and attestation, then return all three objects."""
    chain = load_reliability_evidence_chain(chain_path)
    verify_reliability_evidence_chain(chain, root=root)
    transition = transition_reliability_state(
        subject_id,
        chain,
        store=JsonlReliabilityStateStore(history),
        actor="scenario-runner",
        occurred_at=now,
        evidence_root=root,
    )
    attestation_store = JsonlReliabilityOutcomeAttestationStore(
        root / "attestations.jsonl"
    )
    attestation = attest_reliability_outcome(
        chain,
        transition,
        actor="scenario-runner",
        store=attestation_store,
        occurred_at=now,
    )
    attestation_path = root / f"attestation-{transition.to_state}.json"
    write_reliability_outcome_attestation(attestation, attestation_path)
    report = verify_reliability_outcome(
        attestation,
        chain,
        subject_id=subject_id,
        history_path=history,
        evidence_root=root,
    )
    return attestation, report, attestation_path


def run_scenario(scenario: Scenario) -> dict[str, object]:
    """Execute the full offline reliability lifecycle for one scenario."""
    with TemporaryDirectory() as directory:
        root = Path(directory)
        run, state, evidence, provenance, integrity, chain_path = _prepare_root(
            root, scenario
        )
        receipt_path = _prepare_receipt(
            root,
            evidence=evidence,
            scenario=scenario,
            run_id=f"run-{scenario.scenario_id}",
        )
        subject_id = f"subject-{scenario.scenario_id}"
        history = root / "history.jsonl"

        # Recovery is a lifecycle claim, so prove the predecessor failure first.
        if scenario.reliability_state == "recovered":
            precursor = replace(
                scenario,
                decision="reject",
                reliability_state="unreliable",
                rationale=("port delay made the previous committed route unreliable",),
            )
            precursor_chain_path = root / "precursor-chain.json"
            _build_chain(
                root,
                precursor,
                run=run,
                state=state,
                evidence=evidence,
                provenance=provenance,
                integrity=integrity,
                chain_path=precursor_chain_path,
                receipt_path=receipt_path,
            )
            _, precursor_report, _ = _execute_outcome(
                root=root,
                chain_path=precursor_chain_path,
                subject_id=subject_id,
                history=history,
                now=NOW,
            )
            precursor_ok = precursor_report.verified
        else:
            precursor_ok = True

        _build_chain(
            root,
            scenario,
            run=run,
            state=state,
            evidence=evidence,
            provenance=provenance,
            integrity=integrity,
            chain_path=chain_path,
            receipt_path=receipt_path,
        )
        attestation, report, attestation_path = _execute_outcome(
            root=root,
            chain_path=chain_path,
            subject_id=subject_id,
            history=history,
            now=NOW,
        )

        proof_path = root / "proof.zip"
        build_reliability_proof_bundle(
            attestation_path=attestation_path,
            evidence_chain_path=chain_path,
            history_path=history,
            evidence_root=root,
            output=proof_path,
        )
        proof_report, descriptor = verify_reliability_proof_bundle(proof_path)

        original_bytes = evidence.read_bytes()
        evidence.write_bytes(original_bytes + b"\nTAMPERED")
        try:
            verify_reliability_evidence_chain(
                load_reliability_evidence_chain(chain_path), root=root
            )
        except (ValueError, FileNotFoundError):
            tamper_rejected = True
        else:
            tamper_rejected = False
        evidence.write_bytes(original_bytes)
        verify_reliability_evidence_chain(
            load_reliability_evidence_chain(chain_path), root=root
        )

        return {
            "scenario": scenario.scenario_id,
            "title": scenario.title,
            "decision": scenario.decision,
            "reliability_state": scenario.reliability_state,
            "chain_verified": True,
            "outcome_verified": report.verified,
            "proof_bundle_verified": proof_report.verified,
            "proof_sources": len(descriptor.sources),
            "tamper_rejected": tamper_rejected,
            "precursor_verified": precursor_ok,
            "checks": list(report.checks),
            "attestation_id": attestation.attestation_id,
        }


def main() -> None:
    """Run all scenarios and fail unless every reliability assertion succeeds."""
    results = [run_scenario(scenario) for scenario in SCENARIOS]
    failures = [
        item
        for item in results
        if not all(
            item[key]
            for key in (
                "chain_verified",
                "outcome_verified",
                "proof_bundle_verified",
                "tamper_rejected",
            )
        )
    ]
    print(
        json.dumps(
            {
                "scenario_count": len(results),
                "scenarios": results,
                "passed": not failures,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
