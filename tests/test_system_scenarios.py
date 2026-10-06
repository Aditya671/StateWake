"""Tests for the independent-oracle real-system validation harness."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.testing.system_trial import (
    TrialContractError,
    _evaluate_run,
    _external_result,
    analyze_campaign,
    generate_datasets,
    load_scenarios,
    main,
    run_campaign,
    validate_datasets,
    write_reports,
)


def test_generate_validate_run_and_analyze_local_controls(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    workspaces = tmp_path / "workspaces"
    evidence = tmp_path / "evidence"
    reports = tmp_path / "reports"

    scenarios = generate_datasets(inputs, seed=4242)
    assert [item.scenario_id for item in scenarios] == [
        "PAYMENT-IDEMPOTENCY-001",
        "RAG-STALE-CORPUS-001",
        "AGENT-AUTH-001",
    ]
    assert len(validate_datasets(inputs)) == 3

    results = run_campaign(inputs, workspaces, evidence, offline=True)
    assert len(results) == 9
    assert {item.status for item in results} == {"PASS"}
    assert not any(item.forbidden_observations_seen for item in results)

    golden_rows = [
        json.loads(line)
        for line in (evidence / "golden-baseline-results.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    assert [row["application"] for row in golden_rows] == [
        "payment-reliability",
        "enterprise-ai-reliability",
        "municipal-decision-reliability",
    ]
    assert {row["status"] for row in golden_rows} == {"PASS"}
    assert all(row["stdout_sha256"] for row in golden_rows)
    assert all("evidence_receipt_id" not in row for row in golden_rows)

    metrics, _, loaded = analyze_campaign(inputs, evidence)
    assert len(loaded) == 9
    assert metrics.capture_coverage == 1.0
    assert metrics.evidence_completeness == 1.0
    assert metrics.false_assurance_count == 0
    assert metrics.reconstructability == 1.0
    assert metrics.fault_recall is not None
    assert 0.0 < metrics.fault_recall < 1.0
    assert metrics.fault_precision == 1.0
    assert metrics.privacy_leakage_count == 0

    written = write_reports(inputs, evidence, reports)
    assert written == metrics
    for name in (
        "REAL_SYSTEM_VALIDATION_REPORT.md",
        "COVERAGE_MATRIX.csv",
        "DEFECT_REGISTER.md",
        "REPRODUCIBILITY_REPORT.md",
        "VALUE_ASSESSMENT.md",
    ):
        assert (reports / name).is_file()
    value = (reports / "VALUE_ASSESSMENT.md").read_text(encoding="utf-8")
    assert "NOT_MEASURED" in value


def test_dataset_validation_rejects_tampered_fixture(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    generate_datasets(inputs, seed=4242)
    (inputs / "fixtures" / "rag.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(TrialContractError, match="fixture digest mismatch"):
        validate_datasets(inputs)


def test_scenario_schema_rejects_unknown_field(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    generate_datasets(inputs, seed=4242)
    catalog = inputs / "scenario_catalog.jsonl"
    rows = catalog.read_text(encoding="utf-8").splitlines()
    payload = json.loads(rows[0])
    payload["stronger_assurance"] = True
    rows[0] = json.dumps(payload, sort_keys=True)
    catalog.write_text("\n".join(rows) + "\n", encoding="utf-8")
    with pytest.raises(TrialContractError, match="unknown fields"):
        load_scenarios(inputs)


def test_run_requires_explicit_offline_or_external_boundary(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    generate_datasets(inputs, seed=4242)
    with pytest.raises(TrialContractError, match="network-enabled execution"):
        run_campaign(
            inputs, tmp_path / "workspaces", tmp_path / "evidence", offline=False
        )


def test_missing_external_result_is_blocked_not_pass(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    scenarios = generate_datasets(inputs, seed=4242)
    result = _evaluate_run(scenarios[0], 1, None)
    assert result.status == "BLOCKED_ENV"
    assert result.reconstructable is False
    assert result.required_observations_missing == scenarios[0].required_observations


def test_privacy_scan_excludes_restricted_directory_but_detects_leak(
    tmp_path: Path,
) -> None:
    inputs = tmp_path / "inputs"
    evidence = tmp_path / "evidence"
    generate_datasets(inputs, seed=4242)
    run_campaign(inputs, tmp_path / "workspaces", evidence, offline=True)
    privacy = evidence / "privacy"
    privacy.mkdir()
    (privacy / "restricted.txt").write_text("SW_TEST_SECRET_ALLOWED", encoding="utf-8")
    metrics, _, _ = analyze_campaign(inputs, evidence)
    assert metrics.privacy_leakage_count == 0
    (evidence / "leak.txt").write_text("SW_TEST_SECRET_LEAK", encoding="utf-8")
    metrics, _, _ = analyze_campaign(inputs, evidence)
    assert metrics.privacy_leakage_count == 1


def test_cli_target_interface(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    inputs = tmp_path / "inputs"
    evidence = tmp_path / "evidence"
    workspaces = tmp_path / "workspaces"
    reports = tmp_path / "reports"
    assert main(["generate", "--seed", "4242", "--output", str(inputs)]) == 0
    assert main(["validate-datasets", "--input", str(inputs)]) == 0
    assert (
        main(
            [
                "run",
                "--input",
                str(inputs),
                "--workspaces",
                str(workspaces),
                "--evidence",
                str(evidence),
                "--offline",
            ]
        )
        == 0
    )
    assert (
        main(
            [
                "analyze",
                "--input",
                str(inputs),
                "--evidence",
                str(evidence),
                "--reports",
                str(reports),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert '"status": "PASS"' in output


def test_generated_dataset_contains_plan_required_catalog_files(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    generate_datasets(inputs, seed=4242)
    for name in (
        "scenario_catalog.jsonl",
        "seed_documents.jsonl",
        "seed_requests.jsonl",
        "expected_oracles.jsonl",
        "mutations.jsonl",
        "dataset_manifest.json",
        "dataset_manifest.sha256",
    ):
        assert (inputs / name).is_file()
    validate_datasets(inputs)


def test_event_ledger_preserves_explicit_unknown_fields(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    evidence = tmp_path / "evidence"
    generate_datasets(inputs, seed=4242)
    run_campaign(inputs, tmp_path / "workspaces", evidence, offline=True)
    first = json.loads(
        (evidence / "event-ledger.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert first["logical_run_id"] == "PAYMENT-IDEMPOTENCY-001"
    assert "producer_id" in first
    assert "native_event_id" in first
    assert "contract_type" in first
    assert "profile_decision" in first
    assert "exception_class" in first
    assert first["native_event_id"] is None
    assert first["profile_id"] is None


def test_external_result_envelope_keeps_truth_and_observations_separate(
    tmp_path: Path,
) -> None:
    inputs = tmp_path / "inputs"
    evidence = tmp_path / "evidence"
    scenario = generate_datasets(inputs, seed=4242)[0]
    imports = evidence / "imports"
    imports.mkdir(parents=True)
    envelope = {
        "schema_version": 1,
        "scenario_id": scenario.scenario_id,
        "repeat": 1,
        "fault_injection_effective": True,
        "host_storage_bytes": 12,
        "notes": ["external fixture"],
        "truth": [
            {
                "event_key": "host.effect",
                "value": "committed",
                "source": "independent-host-ledger",
                "expected_observation_key": "capture.effect",
                "timestamp_utc": "2026-09-30T00:00:00+00:00",
            }
        ],
        "observations": [
            {
                "observation_key": "capture.effect",
                "logical_run_id": scenario.scenario_id,
                "producer_id": None,
                "source_event_id": None,
                "native_event_id": None,
                "contract_type": None,
                "contract_digest": None,
                "receipt_id": None,
                "state_before": None,
                "state_after": None,
                "profile_id": None,
                "profile_decision": None,
                "expected": "recorded effect",
                "actual": "committed",
                "detector": "external-host-check",
                "timestamp_utc": "2026-09-30T00:00:01+00:00",
                "exception_class": None,
                "reason": None,
                "evidence_path": None,
            }
        ],
    }
    path = imports / f"{scenario.scenario_id}.1.json"
    path.write_text(json.dumps(envelope), encoding="utf-8")
    result = _external_result(scenario, 1, evidence)
    assert result is not None
    assert result.truth[0].source == "independent-host-ledger"
    assert result.observations[0].observation_key == "capture.effect"


def test_external_result_rejects_unknown_assurance_field(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    evidence = tmp_path / "evidence"
    scenario = generate_datasets(inputs, seed=4242)[0]
    imports = evidence / "imports"
    imports.mkdir(parents=True)
    envelope = {
        "schema_version": 1,
        "scenario_id": scenario.scenario_id,
        "repeat": 1,
        "fault_injection_effective": True,
        "host_storage_bytes": 0,
        "notes": [],
        "truth": [],
        "observations": [
            {
                "observation_key": "capture.effect",
                "expected": "recorded",
                "actual": "recorded",
                "detector": None,
                "timestamp_utc": "2026-09-30T00:00:00+00:00",
                "universal_truth_verified": True,
            }
        ],
    }
    path = imports / f"{scenario.scenario_id}.1.json"
    path.write_text(json.dumps(envelope), encoding="utf-8")
    with pytest.raises(TrialContractError, match="unknown fields"):
        _external_result(scenario, 1, evidence)
