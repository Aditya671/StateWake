"""CI/CD evidence producer integration for release and build events."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from statewake.ai_contracts.evaluator import EvaluatorEvidenceContract
from statewake.ai_contracts.policy import PolicyEvidenceContract

from .base import (
    ContractCaptureResult,
    capture_contract,
    digest_json,
    json_object_from_mapping,
    metadata_without_payload,
    parse_time,
    required_string,
)


def capture_cicd_release_event(event: Mapping[str, Any]) -> ContractCaptureResult:
    """Map a CI/CD release gate event into policy evidence.

    The adapter records the release decision boundary only. It does not build,
    scan, sign, publish, or approve the artifact.
    """
    data = dict(event)
    contract = PolicyEvidenceContract(
        contract_version="cicd.release.policy.v1",
        producer_id=required_string(data.get("producer_id"), field="producer_id"),
        run_id=required_string(data.get("run_id"), field="run_id"),
        policy_id=required_string(data.get("policy_id"), field="policy_id"),
        policy_version=required_string(
            data.get("policy_version"), field="policy_version"
        ),
        decision=required_string(data.get("decision"), field="decision"),
        rationale_digest=digest_json(
            json_object_from_mapping(
                data.get("rationale", {"decision": data.get("decision")}),
                field="rationale",
            )
        ),
        residual_risk=str(data.get("residual_risk", "not stated")),
        captured_at=parse_time(data.get("captured_at")),
        metadata=metadata_without_payload(
            data,
            exclude={"rationale", "captured_at"},
        ),
    )
    return capture_contract(contract)


def capture_cicd_test_result(event: Mapping[str, Any]) -> ContractCaptureResult:
    """Map CI/CD test summary output into evaluator evidence."""
    data = dict(event)
    metric_values = json_object_from_mapping(
        data.get("metric_values", {"passed": data.get("passed", 0)}),
        field="metric_values",
    )
    thresholds = json_object_from_mapping(
        data.get("thresholds", {"required_state": "pass"}), field="thresholds"
    )
    contract = EvaluatorEvidenceContract(
        contract_version="cicd.test.evaluator.v1",
        producer_id=required_string(data.get("producer_id"), field="producer_id"),
        run_id=required_string(data.get("run_id"), field="run_id"),
        evaluator_id=required_string(
            data.get("evaluator_id", data.get("job_name", "ci-tests")),
            field="evaluator_id",
        ),
        evaluator_version=required_string(
            data.get("evaluator_version", "ci-system"), field="evaluator_version"
        ),
        metric_version=required_string(
            data.get("metric_version", "ci-test-summary.v1"), field="metric_version"
        ),
        metric_values=metric_values,
        thresholds=thresholds,
        dataset_identity=required_string(
            data.get("dataset_identity", data.get("artifact_digest", "ci-run")),
            field="dataset_identity",
        ),
        evaluator_limitations=str(
            data.get("evaluator_limitations", "CI results only.")
        ),
        captured_at=parse_time(data.get("captured_at")),
        metadata=metadata_without_payload(
            data,
            exclude={"metric_values", "thresholds", "captured_at"},
        ),
    )
    return capture_contract(contract)
