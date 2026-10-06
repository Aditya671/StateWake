"""Independent-oracle real-system validation harness for StateWake.

This module is testing/research infrastructure. It does not add a StateWake
runtime authority and it never treats StateWake's own output as ground truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Final, Literal, cast

from statewake import (
    AgentEvidenceAdapter,
    AgentRunEvidence,
    IdentityConflictError,
    IntegrationContext,
    StateWakeClient,
    WebhookEvent,
    WebhookEvidenceAdapter,
)

SCHEMA_VERSION: Final = 1
ALLOWED_OUTCOMES: Final = frozenset(
    {
        "PASS",
        "FAIL_STATEWAKE",
        "FAIL_HOST",
        "FAIL_INTEGRATION",
        "INCONCLUSIVE",
        "BLOCKED_ENV",
        "NOT_APPLICABLE",
    }
)
RunnerName = Literal[
    "local-payment-control",
    "local-rag-control",
    "local-tool-control",
    "external",
]
Outcome = Literal[
    "PASS",
    "FAIL_STATEWAKE",
    "FAIL_HOST",
    "FAIL_INTEGRATION",
    "INCONCLUSIVE",
    "BLOCKED_ENV",
    "NOT_APPLICABLE",
]
Severity = Literal["low", "medium", "high", "critical"]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
GOLDEN_APPS: Final = (
    ("payment-reliability", "examples/golden/payment_reliability.py"),
    ("enterprise-ai-reliability", "examples/golden/enterprise_ai_reliability.py"),
    (
        "municipal-decision-reliability",
        "examples/golden/municipal_decision_reliability.py",
    ),
)


class TrialContractError(ValueError):
    """Raised when a trial input or result violates the harness contract."""


@dataclass(frozen=True, slots=True)
class InjectionSpec:
    """One declared fault injection for a scenario."""

    point: str
    mutation: str


@dataclass(frozen=True, slots=True)
class ScenarioSpec:
    """One immutable system-trial scenario definition."""

    scenario_id: str
    scenario_version: int
    seed: int
    host_application: str
    runner: RunnerName
    capabilities: tuple[str, ...]
    preconditions: tuple[str, ...]
    input_fixture: str
    input_sha256: str
    injection: InjectionSpec | None
    host_expected: str
    statewake_expected: str
    required_observations: tuple[str, ...]
    forbidden_observations: tuple[str, ...]
    oracle: str
    severity_if_wrong: Severity
    repeat_count: int


@dataclass(frozen=True, slots=True)
class TruthEvent:
    """One independently maintained host-side truth observation."""

    scenario_id: str
    repeat: int
    sequence: int
    event_key: str
    value: str
    source: str
    expected_observation_key: str | None
    timestamp_utc: str


@dataclass(frozen=True, slots=True)
class ObservationEvent:
    """One StateWake-side observation or validator outcome."""

    scenario_id: str
    repeat: int
    sequence: int
    observation_key: str
    logical_run_id: str | None
    producer_id: str | None
    source_event_id: str | None
    native_event_id: str | None
    contract_type: str | None
    contract_digest: str | None
    receipt_id: str | None
    state_before: str | None
    state_after: str | None
    profile_id: str | None
    profile_decision: str | None
    expected: str
    actual: str
    detector: str | None
    timestamp_utc: str
    exception_class: str | None
    reason: str | None
    evidence_path: str | None


@dataclass(frozen=True, slots=True)
class Measurement:
    """One matched workload measurement recorded by the harness."""

    scenario_id: str
    repeat: int
    wall_ms: float
    statewake_storage_bytes: int
    host_storage_bytes: int


@dataclass(frozen=True, slots=True)
class ScenarioRunResult:
    """Result of one scenario repetition."""

    scenario_id: str
    repeat: int
    status: Outcome
    fault_injection_effective: bool | None
    detected_fault: bool | None
    required_observations_met: tuple[str, ...]
    required_observations_missing: tuple[str, ...]
    forbidden_observations_seen: tuple[str, ...]
    reconstructable: bool
    notes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class OperatorAssessment:
    """One paired operator diagnosis timing record."""

    scenario_id: str
    reviewer_id: str
    without_statewake_seconds: float
    with_statewake_seconds: float
    without_statewake_correct: bool
    with_statewake_correct: bool
    unsupported_assertions_without: int
    unsupported_assertions_with: int


@dataclass(frozen=True, slots=True)
class CampaignMetrics:
    """Decision-usefulness metrics derived only from recorded evidence."""

    scenario_runs: int
    passed_runs: int
    blocked_runs: int
    capture_coverage: float | None
    evidence_completeness: float | None
    fault_recall: float | None
    fault_precision: float | None
    false_assurance_count: int
    reconstructability: float | None
    diagnostic_gain_seconds_median: float | None
    wall_ms_p50: float | None
    wall_ms_p95: float | None
    wall_ms_p99: float | None
    privacy_leakage_count: int


@dataclass(frozen=True, slots=True)
class GoldenBaselineResult:
    """One execution result from an existing StateWake golden reference app."""

    application: str
    script: str
    status: Literal["PASS", "FAIL_INTEGRATION"]
    returncode: int | None
    wall_ms: float
    stdout_sha256: str | None
    stderr_sha256: str | None
    reason: str | None


@dataclass(frozen=True, slots=True)
class _RunnerOutput:
    truth: tuple[TruthEvent, ...]
    observations: tuple[ObservationEvent, ...]
    fault_injection_effective: bool | None
    notes: tuple[str, ...]
    host_storage_bytes: int


def _now() -> str:
    """Return one UTC timestamp for recorded trial evidence."""
    return datetime.now(UTC).isoformat()


def _canonical_json(payload: object) -> bytes:
    """Encode one JSON-compatible object deterministically."""
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    """Return lowercase SHA-256 for bytes."""
    return sha256(payload).hexdigest()


def _require_string(value: object, field: str) -> str:
    """Require a non-blank string field."""
    if not isinstance(value, str) or not value.strip():
        raise TrialContractError(f"{field} must be a non-blank string")
    return value


def _optional_text(item: dict[object, object], name: str) -> str | None:
    """Return an optional validated string from one external observation object."""
    raw = item.get(name)
    if raw is None:
        return None
    return _require_string(raw, f"observation.{name}")


def _require_string_list(value: object, field: str) -> tuple[str, ...]:
    """Require a JSON array containing unique non-blank strings."""
    if not isinstance(value, list):
        raise TrialContractError(f"{field} must be an array")
    result = tuple(_require_string(item, field) for item in value)
    if len(set(result)) != len(result):
        raise TrialContractError(f"{field} must not contain duplicates")
    return result


def _require_int(value: object, field: str, *, minimum: int = 0) -> int:
    """Require a non-boolean integer at or above ``minimum``."""
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise TrialContractError(f"{field} must be an integer >= {minimum}")
    return value


def _require_float(value: object, field: str, *, minimum: float = 0.0) -> float:
    """Require a numeric value at or above ``minimum``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TrialContractError(f"{field} must be numeric")
    result = float(value)
    if result < minimum:
        raise TrialContractError(f"{field} must be >= {minimum}")
    return result


def _safe_relative_path(value: object, field: str) -> str:
    """Require a relative path without traversal or an absolute root."""
    raw = _require_string(value, field)
    path = Path(raw)
    if path.is_absolute() or ".." in path.parts:
        raise TrialContractError(f"{field} must stay inside the dataset root")
    return path.as_posix()


def _scenario_from_dict(payload: object) -> ScenarioSpec:
    """Parse and strictly validate one scenario JSON object."""
    if not isinstance(payload, dict):
        raise TrialContractError("scenario record must be an object")
    allowed = {
        "schema_version",
        "scenario_id",
        "scenario_version",
        "seed",
        "host_application",
        "runner",
        "capabilities",
        "preconditions",
        "input_fixture",
        "input_sha256",
        "injection",
        "host_expected",
        "statewake_expected",
        "required_observations",
        "forbidden_observations",
        "oracle",
        "severity_if_wrong",
        "repeat_count",
        "status",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise TrialContractError(f"scenario contains unknown fields: {sorted(unknown)}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise TrialContractError("unsupported system-trial scenario schema")
    if payload.get("status") != "NOT_RUN":
        raise TrialContractError("scenario catalog status must start as NOT_RUN")
    runner = _require_string(payload.get("runner"), "runner")
    if runner not in {
        "local-payment-control",
        "local-rag-control",
        "local-tool-control",
        "external",
    }:
        raise TrialContractError("unsupported scenario runner")
    severity = _require_string(payload.get("severity_if_wrong"), "severity_if_wrong")
    if severity not in {"low", "medium", "high", "critical"}:
        raise TrialContractError("unsupported severity_if_wrong")
    injection_raw = payload.get("injection")
    injection: InjectionSpec | None = None
    if injection_raw is not None:
        if not isinstance(injection_raw, dict) or set(injection_raw) != {
            "point",
            "mutation",
        }:
            raise TrialContractError(
                "injection must contain exactly point and mutation"
            )
        injection = InjectionSpec(
            _require_string(injection_raw.get("point"), "injection.point"),
            _require_string(injection_raw.get("mutation"), "injection.mutation"),
        )
    digest = _require_string(payload.get("input_sha256"), "input_sha256")
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise TrialContractError("input_sha256 must be lowercase SHA-256 hex")
    return ScenarioSpec(
        scenario_id=_require_string(payload.get("scenario_id"), "scenario_id"),
        scenario_version=_require_int(
            payload.get("scenario_version"), "scenario_version", minimum=1
        ),
        seed=_require_int(payload.get("seed"), "seed"),
        host_application=_require_string(
            payload.get("host_application"), "host_application"
        ),
        runner=cast(RunnerName, runner),
        capabilities=_require_string_list(payload.get("capabilities"), "capabilities"),
        preconditions=_require_string_list(
            payload.get("preconditions"), "preconditions"
        ),
        input_fixture=_safe_relative_path(
            payload.get("input_fixture"), "input_fixture"
        ),
        input_sha256=digest,
        injection=injection,
        host_expected=_require_string(payload.get("host_expected"), "host_expected"),
        statewake_expected=_require_string(
            payload.get("statewake_expected"), "statewake_expected"
        ),
        required_observations=_require_string_list(
            payload.get("required_observations"), "required_observations"
        ),
        forbidden_observations=_require_string_list(
            payload.get("forbidden_observations"), "forbidden_observations"
        ),
        oracle=_require_string(payload.get("oracle"), "oracle"),
        severity_if_wrong=cast(Severity, severity),
        repeat_count=_require_int(
            payload.get("repeat_count"), "repeat_count", minimum=1
        ),
    )


def _read_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    """Read strict object-per-line JSONL."""
    if not path.is_file():
        raise TrialContractError(f"required JSONL file is missing: {path}")
    records: list[dict[str, object]] = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            raise TrialContractError(f"{path}:{line_number}: blank JSONL row")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise TrialContractError(
                f"{path}:{line_number}: invalid JSON: {exc.msg}"
            ) from exc
        if not isinstance(parsed, dict):
            raise TrialContractError(f"{path}:{line_number}: row must be an object")
        records.append(cast(dict[str, object], parsed))
    return tuple(records)


def _write_jsonl(path: Path, records: tuple[dict[str, object], ...]) -> None:
    """Write deterministic JSONL records."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n"
        for record in records
    )
    path.write_text(text, encoding="utf-8")


def load_scenarios(input_root: Path) -> tuple[ScenarioSpec, ...]:
    """Load and validate the complete scenario catalog and fixture digests."""
    scenarios = tuple(
        _scenario_from_dict(item)
        for item in _read_jsonl(input_root / "scenario_catalog.jsonl")
    )
    if not scenarios:
        raise TrialContractError("scenario catalog must not be empty")
    ids = [item.scenario_id for item in scenarios]
    if len(set(ids)) != len(ids):
        raise TrialContractError("scenario_id values must be unique")
    for scenario in scenarios:
        fixture = (input_root / scenario.input_fixture).resolve()
        root = input_root.resolve()
        if root not in fixture.parents and fixture != root:
            raise TrialContractError("scenario fixture escaped dataset root")
        if not fixture.is_file():
            raise TrialContractError(
                f"scenario {scenario.scenario_id} fixture is missing: {fixture}"
            )
        actual = _sha256_bytes(fixture.read_bytes())
        if actual != scenario.input_sha256:
            raise TrialContractError(
                f"scenario {scenario.scenario_id} fixture digest mismatch"
            )
    return scenarios


def _scenario_record(spec: ScenarioSpec) -> dict[str, object]:
    """Serialize a scenario catalog record."""
    return {
        "schema_version": SCHEMA_VERSION,
        "scenario_id": spec.scenario_id,
        "scenario_version": spec.scenario_version,
        "seed": spec.seed,
        "host_application": spec.host_application,
        "runner": spec.runner,
        "capabilities": list(spec.capabilities),
        "preconditions": list(spec.preconditions),
        "input_fixture": spec.input_fixture,
        "input_sha256": spec.input_sha256,
        "injection": None if spec.injection is None else asdict(spec.injection),
        "host_expected": spec.host_expected,
        "statewake_expected": spec.statewake_expected,
        "required_observations": list(spec.required_observations),
        "forbidden_observations": list(spec.forbidden_observations),
        "oracle": spec.oracle,
        "severity_if_wrong": spec.severity_if_wrong,
        "repeat_count": spec.repeat_count,
        "status": "NOT_RUN",
    }


def generate_datasets(output_root: Path, *, seed: int) -> tuple[ScenarioSpec, ...]:
    """Generate deterministic local-control datasets and immutable fixture digests."""
    fixtures = output_root / "fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    payloads: dict[str, dict[str, object]] = {
        "payment.json": {
            "request_id": "evt-payment-001",
            "body": {"event": "payment_intent.succeeded", "payment_id": "pi-demo-001"},
            "conflicting_body": {
                "event": "payment_intent.failed",
                "payment_id": "pi-demo-001",
            },
        },
        "rag.json": {
            "query": "How long after purchase is a refund allowed?",
            "retrieved_document": "alpha-policy-v1",
            "retrieved_answer": "30 days",
            "current_document": "alpha-policy-v2",
            "current_answer": "14 days",
        },
        "tool.json": {
            "request_id": "refund-600-001",
            "amount": 600,
            "approval_threshold": 500,
            "policy_version": "refund-policy-v1",
            "expected_effect_count": 0,
        },
    }
    fixture_digests: dict[str, str] = {}
    for name, payload in payloads.items():
        encoded = _canonical_json(payload) + b"\n"
        path = fixtures / name
        path.write_bytes(encoded)
        fixture_digests[name] = _sha256_bytes(encoded)

    scenarios = (
        ScenarioSpec(
            scenario_id="PAYMENT-IDEMPOTENCY-001",
            scenario_version=1,
            seed=seed,
            host_application="payment-simulator",
            runner="local-payment-control",
            capabilities=("webhook_evidence", "evidence_receipt", "workspace"),
            preconditions=("synthetic data only", "no real payment side effect"),
            input_fixture="fixtures/payment.json",
            input_sha256=fixture_digests["payment.json"],
            injection=InjectionSpec(
                "webhook.delivery", "same identity with changed bytes"
            ),
            host_expected="one logical synthetic payment event; duplicate does not add a second effect",
            statewake_expected="identical duplicate is idempotent and changed bytes under the same event identity are rejected",
            required_observations=(
                "capture.receipt.verified",
                "capture.duplicate.idempotent",
                "detector.identity_conflict",
            ),
            forbidden_observations=("capture.changed_bytes.accepted",),
            oracle="independent synthetic payment effect ledger + frozen webhook bytes",
            severity_if_wrong="critical",
            repeat_count=3,
        ),
        ScenarioSpec(
            scenario_id="RAG-STALE-CORPUS-001",
            scenario_version=1,
            seed=seed,
            host_application="rag-assistant",
            runner="local-rag-control",
            capabilities=("agent_evidence", "retrieval_identity", "workspace"),
            preconditions=("synthetic corpus only", "no external model call"),
            input_fixture="fixtures/rag.json",
            input_sha256=fixture_digests["rag.json"],
            injection=InjectionSpec(
                "retrieval.corpus", "source updated after v1 retrieval"
            ),
            host_expected="the answer is based on the v1 document while the current corpus is v2",
            statewake_expected="captured retrieval identity remains bound to v1 and must not be rewritten as v2",
            required_observations=(
                "capture.receipt.verified",
                "capture.retrieval.v1",
            ),
            forbidden_observations=(
                "capture.retrieval.v2",
                "assurance.current_source_used",
            ),
            oracle="independent versioned corpus ledger + captured agent evidence",
            severity_if_wrong="high",
            repeat_count=3,
        ),
        ScenarioSpec(
            scenario_id="AGENT-AUTH-001",
            scenario_version=1,
            seed=seed,
            host_application="agent-tool-workflow",
            runner="local-tool-control",
            capabilities=("agent_evidence", "policy_reference", "workspace"),
            preconditions=("synthetic refund only", "real side effect disabled"),
            input_fixture="fixtures/tool.json",
            input_sha256=fixture_digests["tool.json"],
            injection=InjectionSpec(
                "tool.authorization", "approval omitted above threshold"
            ),
            host_expected="policy denies execution and the synthetic refund effect count remains zero",
            statewake_expected="capture preserves the denial reference and does not invent a tool-result effect",
            required_observations=(
                "capture.receipt.verified",
                "capture.policy.denied",
            ),
            forbidden_observations=(
                "capture.tool_effect.present",
                "assurance.tool_authorized",
            ),
            oracle="independent policy engine + tool-effect ledger",
            severity_if_wrong="critical",
            repeat_count=3,
        ),
    )
    _write_jsonl(
        output_root / "scenario_catalog.jsonl",
        tuple(_scenario_record(item) for item in scenarios),
    )
    _write_jsonl(
        output_root / "seed_requests.jsonl",
        tuple(
            {
                "schema_version": SCHEMA_VERSION,
                "scenario_id": item.scenario_id,
                "input_fixture": item.input_fixture,
                "input_sha256": item.input_sha256,
            }
            for item in scenarios
        ),
    )
    _write_jsonl(
        output_root / "expected_oracles.jsonl",
        tuple(
            {
                "schema_version": SCHEMA_VERSION,
                "scenario_id": item.scenario_id,
                "host_expected": item.host_expected,
                "statewake_expected": item.statewake_expected,
                "oracle": item.oracle,
                "severity_if_wrong": item.severity_if_wrong,
            }
            for item in scenarios
        ),
    )
    _write_jsonl(
        output_root / "mutations.jsonl",
        tuple(
            {
                "schema_version": SCHEMA_VERSION,
                "scenario_id": item.scenario_id,
                "injection": (
                    None if item.injection is None else asdict(item.injection)
                ),
            }
            for item in scenarios
        ),
    )
    _write_jsonl(
        output_root / "seed_documents.jsonl",
        (
            {
                "schema_version": SCHEMA_VERSION,
                "document_id": "alpha-policy-v1",
                "version": 1,
                "content": "Refunds are allowed within 30 days.",
                "content_sha256": _sha256_bytes(b"Refunds are allowed within 30 days."),
            },
            {
                "schema_version": SCHEMA_VERSION,
                "document_id": "alpha-policy-v2",
                "version": 2,
                "content": "Refunds are allowed within 14 days.",
                "content_sha256": _sha256_bytes(b"Refunds are allowed within 14 days."),
            },
        ),
    )
    dataset_files = {
        path.relative_to(output_root).as_posix(): _sha256_bytes(path.read_bytes())
        for path in sorted(output_root.rglob("*"))
        if path.is_file()
        and path.name not in {"dataset_manifest.json", "dataset_manifest.sha256"}
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "seed": seed,
        "scenario_count": len(scenarios),
        "files": dataset_files,
        "fixtures": {
            relative: digest
            for relative, digest in dataset_files.items()
            if relative.startswith("fixtures/")
        },
    }
    manifest["dataset_digest"] = _sha256_bytes(_canonical_json(manifest))
    manifest_path = output_root / "dataset_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output_root / "dataset_manifest.sha256").write_text(
        f"{_sha256_bytes(manifest_path.read_bytes())}  dataset_manifest.json\n",
        encoding="utf-8",
    )
    return scenarios


def validate_datasets(input_root: Path) -> tuple[ScenarioSpec, ...]:
    """Validate scenario schema, fixture containment, and manifest integrity."""
    scenarios = load_scenarios(input_root)
    manifest_path = input_root / "dataset_manifest.json"
    if not manifest_path.is_file():
        raise TrialContractError("dataset_manifest.json is missing")
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise TrialContractError("unsupported dataset manifest schema")
    supplied = _require_string(payload.get("dataset_digest"), "dataset_digest")
    recompute = dict(payload)
    recompute.pop("dataset_digest", None)
    if _sha256_bytes(_canonical_json(recompute)) != supplied:
        raise TrialContractError("dataset manifest digest mismatch")
    files = payload.get("files")
    if not isinstance(files, dict):
        raise TrialContractError("dataset manifest files must be an object")
    recorded_files: dict[str, str] = {}
    for relative, digest in files.items():
        relative_path = _safe_relative_path(relative, "manifest file path")
        recorded_files[relative_path] = _require_string(digest, "manifest file digest")
    actual_files = {
        path.relative_to(input_root).as_posix(): _sha256_bytes(path.read_bytes())
        for path in sorted(input_root.rglob("*"))
        if path.is_file()
        and path.name not in {"dataset_manifest.json", "dataset_manifest.sha256"}
    }
    if recorded_files != actual_files:
        raise TrialContractError("dataset manifest file set or digest mismatch")

    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, dict):
        raise TrialContractError("dataset manifest fixtures must be an object")
    for relative, digest in fixtures.items():
        relative_path = _safe_relative_path(relative, "manifest fixture path")
        expected = _require_string(digest, "manifest fixture digest")
        path = input_root / relative_path
        if not path.is_file() or _sha256_bytes(path.read_bytes()) != expected:
            raise TrialContractError(
                f"dataset fixture integrity mismatch: {relative_path}"
            )

    sidecar = input_root / "dataset_manifest.sha256"
    if not sidecar.is_file():
        raise TrialContractError("dataset_manifest.sha256 is missing")
    parts = sidecar.read_text(encoding="utf-8").strip().split()
    if len(parts) != 2 or parts[1] != "dataset_manifest.json":
        raise TrialContractError("dataset manifest checksum sidecar is malformed")
    if parts[0] != _sha256_bytes(manifest_path.read_bytes()):
        raise TrialContractError("dataset manifest checksum mismatch")

    scenario_by_id = {item.scenario_id: item for item in scenarios}
    request_rows = _read_jsonl(input_root / "seed_requests.jsonl")
    oracle_rows = _read_jsonl(input_root / "expected_oracles.jsonl")
    mutation_rows = _read_jsonl(input_root / "mutations.jsonl")
    document_rows = _read_jsonl(input_root / "seed_documents.jsonl")
    if len(request_rows) != len(scenarios):
        raise TrialContractError("seed request count does not match scenario catalog")
    if len(oracle_rows) != len(scenarios):
        raise TrialContractError("oracle count does not match scenario catalog")
    if len(mutation_rows) != len(scenarios):
        raise TrialContractError("mutation count does not match scenario catalog")
    for row in request_rows:
        scenario_id = _require_string(
            row.get("scenario_id"), "seed request scenario_id"
        )
        scenario = scenario_by_id.get(scenario_id)
        if scenario is None:
            raise TrialContractError("seed request references unknown scenario")
        if (
            row.get("input_fixture") != scenario.input_fixture
            or row.get("input_sha256") != scenario.input_sha256
        ):
            raise TrialContractError(
                "seed request does not match scenario fixture identity"
            )
    for row in oracle_rows:
        scenario_id = _require_string(row.get("scenario_id"), "oracle scenario_id")
        scenario = scenario_by_id.get(scenario_id)
        if scenario is None:
            raise TrialContractError("oracle references unknown scenario")
        expected_oracle_fields = {
            "host_expected": scenario.host_expected,
            "statewake_expected": scenario.statewake_expected,
            "oracle": scenario.oracle,
            "severity_if_wrong": scenario.severity_if_wrong,
        }
        if any(row.get(key) != value for key, value in expected_oracle_fields.items()):
            raise TrialContractError("oracle record does not match scenario contract")
    for row in mutation_rows:
        scenario_id = _require_string(row.get("scenario_id"), "mutation scenario_id")
        scenario = scenario_by_id.get(scenario_id)
        if scenario is None:
            raise TrialContractError("mutation references unknown scenario")
        expected_injection = (
            None if scenario.injection is None else asdict(scenario.injection)
        )
        if row.get("injection") != expected_injection:
            raise TrialContractError("mutation record does not match scenario contract")
    if not document_rows:
        raise TrialContractError("seed document corpus must not be empty")
    for row in document_rows:
        content = _require_string(row.get("content"), "seed document content")
        if row.get("content_sha256") != _sha256_bytes(content.encode("utf-8")):
            raise TrialContractError("seed document digest mismatch")
    return scenarios


def _event(
    scenario_id: str,
    repeat: int,
    sequence: int,
    key: str,
    value: object,
    *,
    source: str,
    expected_observation_key: str | None = None,
) -> TruthEvent:
    """Build a host-truth event."""
    return TruthEvent(
        scenario_id,
        repeat,
        sequence,
        key,
        str(value),
        source,
        expected_observation_key,
        _now(),
    )


def _observation(
    scenario_id: str,
    repeat: int,
    sequence: int,
    key: str,
    value: object,
    *,
    detector: str | None = None,
    producer_id: str | None = None,
    source_event_id: str | None = None,
    contract_type: str | None = None,
    contract_digest: str | None = None,
    receipt_id: str | None = None,
    expected: str = "recorded observation",
    exception_class: str | None = None,
    reason: str | None = None,
    evidence_path: str | None = None,
) -> ObservationEvent:
    """Build one event-ledger row using the real-system validation vocabulary."""
    return ObservationEvent(
        scenario_id=scenario_id,
        repeat=repeat,
        sequence=sequence,
        observation_key=key,
        logical_run_id=scenario_id,
        producer_id=producer_id,
        source_event_id=source_event_id,
        native_event_id=None,
        contract_type=contract_type,
        contract_digest=contract_digest,
        receipt_id=receipt_id,
        state_before=None,
        state_after=None,
        profile_id=None,
        profile_decision=None,
        expected=expected,
        actual=str(value),
        detector=detector,
        timestamp_utc=_now(),
        exception_class=exception_class,
        reason=reason,
        evidence_path=evidence_path,
    )


def _run_golden_baselines(evidence_root: Path) -> tuple[GoldenBaselineResult, ...]:
    """Execute the three existing golden apps as a no-new-code baseline.

    Golden app output is not host ground truth for trial scenarios. Only bounded
    execution metadata and digests are retained so this baseline cannot become
    a second StateWake oracle.
    """
    results: list[GoldenBaselineResult] = []
    env = os.environ.copy()
    source_path = os.pathsep.join((str(REPO_ROOT / "src"), str(REPO_ROOT)))
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        source_path
        if not existing_pythonpath
        else os.pathsep.join((source_path, existing_pythonpath))
    )
    for application, relative_script in GOLDEN_APPS:
        command = [sys.executable, str(REPO_ROOT / relative_script)]
        start = time.perf_counter()
        try:
            completed = subprocess.run(
                command,
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            wall_ms = (time.perf_counter() - start) * 1000.0
            stdout_bytes = completed.stdout.encode("utf-8")
            stderr_bytes = completed.stderr.encode("utf-8")
            reason: str | None = None
            valid_contract = False
            if completed.returncode == 0:
                try:
                    payload = json.loads(completed.stdout)
                except json.JSONDecodeError:
                    reason = "golden app stdout was not valid JSON"
                else:
                    valid_contract = (
                        isinstance(payload, dict)
                        and payload.get("application") == application
                        and payload.get("chain_verified") is True
                        and payload.get("outcome_verified") is True
                        and payload.get("proof_bundle_verified") is True
                        and payload.get("tamper_rejected") is True
                        and isinstance(payload.get("injected_failure"), str)
                        and bool(payload.get("injected_failure"))
                    )
                    if not valid_contract:
                        reason = (
                            "golden app output did not satisfy its documented "
                            "verification contract"
                        )
            else:
                reason = f"golden app exited with status {completed.returncode}"
            results.append(
                GoldenBaselineResult(
                    application=application,
                    script=relative_script,
                    status="PASS" if valid_contract else "FAIL_INTEGRATION",
                    returncode=completed.returncode,
                    wall_ms=wall_ms,
                    stdout_sha256=_sha256_bytes(stdout_bytes),
                    stderr_sha256=_sha256_bytes(stderr_bytes),
                    reason=reason,
                )
            )
        except subprocess.TimeoutExpired as exc:
            wall_ms = (time.perf_counter() - start) * 1000.0
            raw_stdout = exc.stdout if exc.stdout is not None else b""
            raw_stderr = exc.stderr if exc.stderr is not None else b""
            stdout_bytes = (
                raw_stdout
                if isinstance(raw_stdout, bytes)
                else raw_stdout.encode("utf-8")
            )
            stderr_bytes = (
                raw_stderr
                if isinstance(raw_stderr, bytes)
                else raw_stderr.encode("utf-8")
            )
            results.append(
                GoldenBaselineResult(
                    application=application,
                    script=relative_script,
                    status="FAIL_INTEGRATION",
                    returncode=None,
                    wall_ms=wall_ms,
                    stdout_sha256=_sha256_bytes(stdout_bytes),
                    stderr_sha256=_sha256_bytes(stderr_bytes),
                    reason="golden app exceeded the 60-second baseline timeout",
                )
            )
    _write_jsonl(
        evidence_root / "golden-baseline-results.jsonl",
        tuple(cast(dict[str, object], asdict(item)) for item in results),
    )
    return tuple(results)


def _directory_size(root: Path) -> int:
    """Return total regular-file bytes below ``root``."""
    if not root.exists():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def _load_fixture(input_root: Path, scenario: ScenarioSpec) -> dict[str, object]:
    """Load one already-validated scenario fixture object."""
    parsed = json.loads(
        (input_root / scenario.input_fixture).read_text(encoding="utf-8")
    )
    if not isinstance(parsed, dict):
        raise TrialContractError("fixture root must be an object")
    return cast(dict[str, object], parsed)


def _run_payment(
    scenario: ScenarioSpec, repeat: int, input_root: Path, workspace: Path
) -> _RunnerOutput:
    """Execute a local payment/webhook control with an independent effect ledger."""
    fixture = _load_fixture(input_root, scenario)
    request_id = _require_string(fixture.get("request_id"), "request_id")
    body = _canonical_json(fixture.get("body"))
    conflicting = _canonical_json(fixture.get("conflicting_body"))
    host_effects: dict[str, str] = {}
    host_effects[request_id] = _sha256_bytes(body)
    truth = (
        _event(
            scenario.scenario_id,
            repeat,
            1,
            "host.webhook.received",
            request_id,
            source="host-effect-ledger",
            expected_observation_key="capture.receipt.verified",
        ),
        _event(
            scenario.scenario_id,
            repeat,
            2,
            "host.effect.count",
            len(host_effects),
            source="host-effect-ledger",
        ),
        _event(
            scenario.scenario_id,
            repeat,
            3,
            "host.duplicate.same_bytes",
            True,
            source="frozen-input",
            expected_observation_key="capture.duplicate.idempotent",
        ),
        _event(
            scenario.scenario_id,
            repeat,
            4,
            "host.conflict.changed_bytes",
            True,
            source="frozen-input",
            expected_observation_key="detector.identity_conflict",
        ),
    )
    client = StateWakeClient.for_root(
        IntegrationContext("system-trial-payment", run_id=scenario.scenario_id),
        root=workspace / "statewake",
    )
    adapter = WebhookEvidenceAdapter(client)
    captured_at = datetime(2026, 9, 30, 0, repeat, tzinfo=UTC)
    receipt = adapter.ingest(
        WebhookEvent(request_id, body, "application/json", delivery_attempt=1),
        captured_at=captured_at,
    )
    client.verify_receipt(receipt)
    duplicate = adapter.ingest(
        WebhookEvent(request_id, body, "application/json", delivery_attempt=1),
        captured_at=captured_at,
    )
    observations: list[ObservationEvent] = [
        _observation(
            scenario.scenario_id,
            repeat,
            1,
            "capture.receipt.verified",
            True,
            detector="StateWakeClient.verify_receipt",
            producer_id="system-trial-payment",
            source_event_id=request_id,
            contract_type="webhook",
            contract_digest=receipt.artifact_digest,
            receipt_id=receipt.receipt_id,
            expected="persisted receipt and content-addressed artifact verify",
        ),
        _observation(
            scenario.scenario_id,
            repeat,
            2,
            "capture.duplicate.idempotent",
            duplicate.receipt_id == receipt.receipt_id,
            detector="receipt_identity_equality",
            producer_id="system-trial-payment",
            source_event_id=request_id,
            contract_type="webhook",
            contract_digest=duplicate.artifact_digest,
            receipt_id=duplicate.receipt_id,
            expected="same producer event and bytes retain one receipt identity",
        ),
    ]
    try:
        adapter.ingest(
            WebhookEvent(
                request_id, conflicting, "application/json", delivery_attempt=2
            ),
            captured_at=captured_at,
        )
    except IdentityConflictError:
        observations.append(
            _observation(
                scenario.scenario_id,
                repeat,
                3,
                "detector.identity_conflict",
                True,
                detector="WebhookEvidenceAdapter.identity_conflict",
                producer_id="system-trial-payment",
                source_event_id=request_id,
                contract_type="webhook",
                expected="same event identity with changed bytes is rejected",
                exception_class="IdentityConflictError",
                reason="source-event identity was reused with different content",
            )
        )
    else:
        observations.append(
            _observation(
                scenario.scenario_id,
                repeat,
                3,
                "capture.changed_bytes.accepted",
                True,
            )
        )
    return _RunnerOutput(
        truth,
        tuple(observations),
        True,
        ("host business-effect ledger remained independent from StateWake receipts",),
        len(body) + len(conflicting),
    )


def _run_rag(
    scenario: ScenarioSpec, repeat: int, input_root: Path, workspace: Path
) -> _RunnerOutput:
    """Execute a stale-corpus local control without claiming semantic truth."""
    fixture = _load_fixture(input_root, scenario)
    retrieved_document = _require_string(
        fixture.get("retrieved_document"), "retrieved_document"
    )
    current_document = _require_string(
        fixture.get("current_document"), "current_document"
    )
    retrieved_answer = _require_string(
        fixture.get("retrieved_answer"), "retrieved_answer"
    )
    truth = (
        _event(
            scenario.scenario_id,
            repeat,
            1,
            "host.retrieved_document",
            retrieved_document,
            source="host-retrieval-ledger",
            expected_observation_key="capture.retrieval.v1",
        ),
        _event(
            scenario.scenario_id,
            repeat,
            2,
            "host.current_corpus",
            current_document,
            source="host-corpus-ledger",
        ),
        _event(
            scenario.scenario_id,
            repeat,
            3,
            "host.answer",
            retrieved_answer,
            source="host-output-ledger",
        ),
    )
    client = StateWakeClient.for_root(
        IntegrationContext("system-trial-rag", run_id=scenario.scenario_id),
        root=workspace / "statewake",
    )
    retrieval_ref = (
        f"corpus:{retrieved_document}:{_sha256_bytes(retrieved_document.encode())}"
    )
    agent = AgentRunEvidence(
        run_id=scenario.scenario_id,
        model_id="deterministic-local-stub@1",
        prompt_ref="prompt:refund-window:v1",
        retrieval_ref=retrieval_ref,
        output_ref=f"answer:{_sha256_bytes(retrieved_answer.encode())}",
    )
    receipt = AgentEvidenceAdapter(client).ingest(
        agent,
        captured_at=datetime(2026, 9, 30, 1, repeat, tzinfo=UTC),
    )
    client.verify_receipt(receipt)
    observations = (
        _observation(
            scenario.scenario_id,
            repeat,
            1,
            "capture.receipt.verified",
            True,
            detector="StateWakeClient.verify_receipt",
            producer_id="system-trial-rag",
            source_event_id=scenario.scenario_id,
            contract_type="agent-run",
            contract_digest=receipt.artifact_digest,
            receipt_id=receipt.receipt_id,
            expected="captured agent evidence verifies",
        ),
        _observation(
            scenario.scenario_id,
            repeat,
            2,
            "capture.retrieval.v1",
            retrieval_ref,
            detector="AgentEvidenceAdapter.retrieval_ref",
            producer_id="system-trial-rag",
            source_event_id=scenario.scenario_id,
            contract_type="agent-run",
            contract_digest=receipt.artifact_digest,
            receipt_id=receipt.receipt_id,
            expected="captured retrieval identity remains bound to v1",
        ),
    )
    return _RunnerOutput(
        truth,
        observations,
        True,
        (
            "the control demonstrates preserved retrieval identity; it does not claim StateWake independently detects corpus staleness",
        ),
        len(_canonical_json(fixture)),
    )


def _run_tool(
    scenario: ScenarioSpec, repeat: int, input_root: Path, workspace: Path
) -> _RunnerOutput:
    """Execute a denied synthetic tool action with an independent effect ledger."""
    fixture = _load_fixture(input_root, scenario)
    amount = _require_int(fixture.get("amount"), "amount")
    threshold = _require_int(fixture.get("approval_threshold"), "approval_threshold")
    request_id = _require_string(fixture.get("request_id"), "request_id")
    policy_version = _require_string(fixture.get("policy_version"), "policy_version")
    approved = amount <= threshold
    effects: list[str] = []
    if approved:
        effects.append(request_id)
    truth = (
        _event(
            scenario.scenario_id,
            repeat,
            1,
            "host.policy.approved",
            approved,
            source="independent-policy-engine",
            expected_observation_key="capture.policy.denied",
        ),
        _event(
            scenario.scenario_id,
            repeat,
            2,
            "host.effect.count",
            len(effects),
            source="tool-effect-ledger",
        ),
    )
    client = StateWakeClient.for_root(
        IntegrationContext("system-trial-tool", run_id=scenario.scenario_id),
        root=workspace / "statewake",
    )
    agent = AgentRunEvidence(
        run_id=scenario.scenario_id,
        model_id="deterministic-local-stub@1",
        tool_call_ref=f"tool:refund:{request_id}",
        tool_result_ref=None,
        policy_decision_ref=f"policy:{policy_version}:deny",
        output_ref="decision:approval-required",
    )
    receipt = AgentEvidenceAdapter(client).ingest(
        agent,
        captured_at=datetime(2026, 9, 30, 2, repeat, tzinfo=UTC),
    )
    client.verify_receipt(receipt)
    observations = (
        _observation(
            scenario.scenario_id,
            repeat,
            1,
            "capture.receipt.verified",
            True,
            detector="StateWakeClient.verify_receipt",
            producer_id="system-trial-tool",
            source_event_id=scenario.scenario_id,
            contract_type="agent-run",
            contract_digest=receipt.artifact_digest,
            receipt_id=receipt.receipt_id,
            expected="captured agent evidence verifies",
        ),
        _observation(
            scenario.scenario_id,
            repeat,
            2,
            "capture.policy.denied",
            agent.policy_decision_ref,
            detector="AgentEvidenceAdapter.policy_decision_ref",
            producer_id="system-trial-tool",
            source_event_id=scenario.scenario_id,
            contract_type="agent-run",
            contract_digest=receipt.artifact_digest,
            receipt_id=receipt.receipt_id,
            expected="captured policy decision reference remains a denial",
        ),
    )
    return _RunnerOutput(
        truth,
        observations,
        not approved,
        (
            "tool execution authority remains host-owned; StateWake records the denial reference and absence of a tool result",
        ),
        len(_canonical_json(fixture)),
    )


def _external_result(
    scenario: ScenarioSpec, repeat: int, evidence_root: Path
) -> _RunnerOutput | None:
    """Load an externally produced result envelope for a real host scenario."""
    path = evidence_root / "imports" / f"{scenario.scenario_id}.{repeat}.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise TrialContractError(f"invalid external result envelope: {path}")
    if (
        payload.get("scenario_id") != scenario.scenario_id
        or payload.get("repeat") != repeat
    ):
        raise TrialContractError(f"external result identity mismatch: {path}")
    truth_raw = payload.get("truth")
    obs_raw = payload.get("observations")
    if not isinstance(truth_raw, list) or not isinstance(obs_raw, list):
        raise TrialContractError(
            "external result requires truth and observations arrays"
        )
    truth: list[TruthEvent] = []
    for index, item in enumerate(truth_raw, 1):
        if not isinstance(item, dict):
            raise TrialContractError("external truth item must be an object")
        allowed_truth_fields = {
            "event_key",
            "value",
            "source",
            "expected_observation_key",
            "timestamp_utc",
        }
        unknown = set(item) - allowed_truth_fields
        if unknown:
            raise TrialContractError(
                f"external truth item contains unknown fields: {sorted(unknown)}"
            )
        truth.append(
            TruthEvent(
                scenario.scenario_id,
                repeat,
                index,
                _require_string(item.get("event_key"), "truth.event_key"),
                _require_string(item.get("value"), "truth.value"),
                _require_string(item.get("source"), "truth.source"),
                (
                    None
                    if item.get("expected_observation_key") is None
                    else _require_string(
                        item.get("expected_observation_key"),
                        "truth.expected_observation_key",
                    )
                ),
                _require_string(item.get("timestamp_utc"), "truth.timestamp_utc"),
            )
        )
    observations: list[ObservationEvent] = []
    for index, item in enumerate(obs_raw, 1):
        if not isinstance(item, dict):
            raise TrialContractError("external observation item must be an object")
        detector_raw = item.get("detector")
        if detector_raw is not None and not isinstance(detector_raw, str):
            raise TrialContractError("observation.detector must be string or null")
        allowed_observation_fields = {
            "observation_key",
            "logical_run_id",
            "producer_id",
            "source_event_id",
            "native_event_id",
            "contract_type",
            "contract_digest",
            "receipt_id",
            "state_before",
            "state_after",
            "profile_id",
            "profile_decision",
            "expected",
            "actual",
            "detector",
            "timestamp_utc",
            "exception_class",
            "reason",
            "evidence_path",
        }
        unknown = set(item) - allowed_observation_fields
        if unknown:
            raise TrialContractError(
                f"external observation contains unknown fields: {sorted(unknown)}"
            )

        observations.append(
            ObservationEvent(
                scenario_id=scenario.scenario_id,
                repeat=repeat,
                sequence=index,
                observation_key=_require_string(
                    item.get("observation_key"), "observation.observation_key"
                ),
                logical_run_id=_optional_text(item, "logical_run_id"),
                producer_id=_optional_text(item, "producer_id"),
                source_event_id=_optional_text(item, "source_event_id"),
                native_event_id=_optional_text(item, "native_event_id"),
                contract_type=_optional_text(item, "contract_type"),
                contract_digest=_optional_text(item, "contract_digest"),
                receipt_id=_optional_text(item, "receipt_id"),
                state_before=_optional_text(item, "state_before"),
                state_after=_optional_text(item, "state_after"),
                profile_id=_optional_text(item, "profile_id"),
                profile_decision=_optional_text(item, "profile_decision"),
                expected=_require_string(item.get("expected"), "observation.expected"),
                actual=_require_string(item.get("actual"), "observation.actual"),
                detector=detector_raw,
                timestamp_utc=_require_string(
                    item.get("timestamp_utc"), "observation.timestamp_utc"
                ),
                exception_class=_optional_text(item, "exception_class"),
                reason=_optional_text(item, "reason"),
                evidence_path=_optional_text(item, "evidence_path"),
            )
        )
    effective = payload.get("fault_injection_effective")
    if effective is not None and not isinstance(effective, bool):
        raise TrialContractError("fault_injection_effective must be boolean or null")
    notes = _require_string_list(payload.get("notes", []), "notes")
    host_storage = _require_int(
        payload.get("host_storage_bytes", 0), "host_storage_bytes"
    )
    return _RunnerOutput(
        tuple(truth), tuple(observations), effective, notes, host_storage
    )


def _run_one(
    scenario: ScenarioSpec,
    repeat: int,
    input_root: Path,
    workspace: Path,
    evidence_root: Path,
) -> _RunnerOutput | None:
    """Dispatch one scenario to its explicitly named runner."""
    if scenario.runner == "local-payment-control":
        return _run_payment(scenario, repeat, input_root, workspace)
    if scenario.runner == "local-rag-control":
        return _run_rag(scenario, repeat, input_root, workspace)
    if scenario.runner == "local-tool-control":
        return _run_tool(scenario, repeat, input_root, workspace)
    return _external_result(scenario, repeat, evidence_root)


def _evaluate_run(
    scenario: ScenarioSpec,
    repeat: int,
    output: _RunnerOutput | None,
) -> ScenarioRunResult:
    """Classify one repetition without converting missing evidence into PASS."""
    if output is None:
        return ScenarioRunResult(
            scenario.scenario_id,
            repeat,
            "BLOCKED_ENV",
            None,
            None,
            (),
            scenario.required_observations,
            (),
            False,
            ("external result envelope is unavailable",),
        )
    observation_keys = {item.observation_key for item in output.observations}
    met = tuple(
        item for item in scenario.required_observations if item in observation_keys
    )
    missing = tuple(
        item for item in scenario.required_observations if item not in observation_keys
    )
    forbidden = tuple(
        item for item in scenario.forbidden_observations if item in observation_keys
    )
    detected_fault = None
    if output.fault_injection_effective is True:
        detected_fault = any(
            item.detector is not None and item.observation_key.startswith("detector.")
            for item in output.observations
        )
    status: Outcome = "PASS"
    notes = list(output.notes)
    if output.fault_injection_effective is False:
        status = "INCONCLUSIVE"
        notes.append("declared fault injection did not take effect")
    elif missing or forbidden:
        status = "FAIL_STATEWAKE"
    reconstructable = not missing and not forbidden and bool(output.truth)
    return ScenarioRunResult(
        scenario.scenario_id,
        repeat,
        status,
        output.fault_injection_effective,
        detected_fault,
        met,
        missing,
        forbidden,
        reconstructable,
        tuple(notes),
    )


def run_campaign(
    input_root: Path,
    workspaces_root: Path,
    evidence_root: Path,
    *,
    offline: bool,
) -> tuple[ScenarioRunResult, ...]:
    """Run all configured scenarios and persist separated truth/observation ledgers."""
    if not offline:
        raise TrialContractError(
            "network-enabled execution is intentionally not implicit; use external host result envelopes"
        )
    scenarios = validate_datasets(input_root)
    workspaces_root.mkdir(parents=True, exist_ok=True)
    evidence_root.mkdir(parents=True, exist_ok=True)
    golden_results = _run_golden_baselines(evidence_root)
    failed_golden = tuple(
        item.application for item in golden_results if item.status != "PASS"
    )
    if failed_golden:
        raise TrialContractError(
            "golden reference baseline failed: " + ", ".join(failed_golden)
        )
    all_truth: list[TruthEvent] = []
    all_observations: list[ObservationEvent] = []
    all_measurements: list[Measurement] = []
    results: list[ScenarioRunResult] = []
    for scenario in scenarios:
        for repeat in range(1, scenario.repeat_count + 1):
            workspace = workspaces_root / scenario.scenario_id / f"repeat-{repeat}"
            workspace.mkdir(parents=True, exist_ok=True)
            start = time.perf_counter()
            output = _run_one(scenario, repeat, input_root, workspace, evidence_root)
            wall_ms = (time.perf_counter() - start) * 1000.0
            result = _evaluate_run(scenario, repeat, output)
            results.append(result)
            if output is not None:
                all_truth.extend(output.truth)
                all_observations.extend(output.observations)
                all_measurements.append(
                    Measurement(
                        scenario.scenario_id,
                        repeat,
                        wall_ms,
                        _directory_size(workspace / "statewake"),
                        output.host_storage_bytes,
                    )
                )
    _write_jsonl(
        evidence_root / "truth-ledger.jsonl",
        tuple(cast(dict[str, object], asdict(item)) for item in all_truth),
    )
    _write_jsonl(
        evidence_root / "event-ledger.jsonl",
        tuple(cast(dict[str, object], asdict(item)) for item in all_observations),
    )
    _write_jsonl(
        evidence_root / "measurements.jsonl",
        tuple(cast(dict[str, object], asdict(item)) for item in all_measurements),
    )
    _write_jsonl(
        evidence_root / "scenario-results.jsonl",
        tuple(cast(dict[str, object], asdict(item)) for item in results),
    )
    return tuple(results)


def _load_results(evidence_root: Path) -> tuple[ScenarioRunResult, ...]:
    """Load strict scenario result records generated by this harness."""
    results: list[ScenarioRunResult] = []
    for payload in _read_jsonl(evidence_root / "scenario-results.jsonl"):
        status = _require_string(payload.get("status"), "status")
        if status not in ALLOWED_OUTCOMES:
            raise TrialContractError("unsupported scenario result status")
        effective = payload.get("fault_injection_effective")
        detected = payload.get("detected_fault")
        if effective is not None and not isinstance(effective, bool):
            raise TrialContractError(
                "fault_injection_effective must be boolean or null"
            )
        if detected is not None and not isinstance(detected, bool):
            raise TrialContractError("detected_fault must be boolean or null")
        reconstructable = payload.get("reconstructable")
        if not isinstance(reconstructable, bool):
            raise TrialContractError("reconstructable must be boolean")
        results.append(
            ScenarioRunResult(
                _require_string(payload.get("scenario_id"), "scenario_id"),
                _require_int(payload.get("repeat"), "repeat", minimum=1),
                cast(Outcome, status),
                effective,
                detected,
                _require_string_list(
                    payload.get("required_observations_met"),
                    "required_observations_met",
                ),
                _require_string_list(
                    payload.get("required_observations_missing"),
                    "required_observations_missing",
                ),
                _require_string_list(
                    payload.get("forbidden_observations_seen"),
                    "forbidden_observations_seen",
                ),
                reconstructable,
                _require_string_list(payload.get("notes"), "notes"),
            )
        )
    return tuple(results)


def _load_measurements(evidence_root: Path) -> tuple[Measurement, ...]:
    """Load measurements generated by the harness."""
    path = evidence_root / "measurements.jsonl"
    if not path.exists():
        return ()
    items: list[Measurement] = []
    for payload in _read_jsonl(path):
        items.append(
            Measurement(
                _require_string(payload.get("scenario_id"), "scenario_id"),
                _require_int(payload.get("repeat"), "repeat", minimum=1),
                _require_float(payload.get("wall_ms"), "wall_ms"),
                _require_int(
                    payload.get("statewake_storage_bytes"), "statewake_storage_bytes"
                ),
                _require_int(payload.get("host_storage_bytes"), "host_storage_bytes"),
            )
        )
    return tuple(items)


def _load_operator_assessments(evidence_root: Path) -> tuple[OperatorAssessment, ...]:
    """Load optional paired operator usefulness observations."""
    path = evidence_root / "operator-assessments.jsonl"
    if not path.exists():
        return ()
    items: list[OperatorAssessment] = []
    for payload in _read_jsonl(path):
        without_correct = payload.get("without_statewake_correct")
        with_correct = payload.get("with_statewake_correct")
        if not isinstance(without_correct, bool) or not isinstance(with_correct, bool):
            raise TrialContractError("operator correctness fields must be booleans")
        items.append(
            OperatorAssessment(
                _require_string(payload.get("scenario_id"), "scenario_id"),
                _require_string(payload.get("reviewer_id"), "reviewer_id"),
                _require_float(
                    payload.get("without_statewake_seconds"),
                    "without_statewake_seconds",
                ),
                _require_float(
                    payload.get("with_statewake_seconds"), "with_statewake_seconds"
                ),
                without_correct,
                with_correct,
                _require_int(
                    payload.get("unsupported_assertions_without"),
                    "unsupported_assertions_without",
                ),
                _require_int(
                    payload.get("unsupported_assertions_with"),
                    "unsupported_assertions_with",
                ),
            )
        )
    return tuple(items)


def _percentile(values: tuple[float, ...], percentile: float) -> float | None:
    """Return nearest-rank percentile for a non-empty sample."""
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * percentile + 0.5)))
    return ordered[index]


def _privacy_leakage_count(evidence_root: Path) -> int:
    """Count synthetic secret markers outside the restricted privacy directory."""
    count = 0
    for path in evidence_root.rglob("*"):
        if not path.is_file() or "privacy" in path.relative_to(evidence_root).parts:
            continue
        if path.suffix.lower() not in {".json", ".jsonl", ".md", ".csv", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        count += text.count("SW_TEST_SECRET_")
    return count


def analyze_campaign(
    input_root: Path, evidence_root: Path
) -> tuple[CampaignMetrics, tuple[ScenarioSpec, ...], tuple[ScenarioRunResult, ...]]:
    """Compute campaign metrics from independent ledgers and actual run records."""
    scenarios = validate_datasets(input_root)
    results = _load_results(evidence_root)
    observations = _read_jsonl(evidence_root / "event-ledger.jsonl")
    measurements = _load_measurements(evidence_root)
    assessments = _load_operator_assessments(evidence_root)

    expected_required = 0
    observed_required = 0
    scenario_by_id = {item.scenario_id: item for item in scenarios}
    for result in results:
        scenario = scenario_by_id.get(result.scenario_id)
        if scenario is None:
            raise TrialContractError("scenario result references unknown scenario")
        expected_required += len(scenario.required_observations)
        observed_required += len(result.required_observations_met)

    truth_rows = _read_jsonl(evidence_root / "truth-ledger.jsonl")
    observed_keys = {
        (
            _require_string(item.get("scenario_id"), "scenario_id"),
            _require_int(item.get("repeat"), "repeat", minimum=1),
            _require_string(item.get("observation_key"), "observation_key"),
        )
        for item in observations
    }
    capture_targets: list[tuple[str, int, str]] = []
    for item in truth_rows:
        expected_key = item.get("expected_observation_key")
        if expected_key is None:
            continue
        capture_targets.append(
            (
                _require_string(item.get("scenario_id"), "scenario_id"),
                _require_int(item.get("repeat"), "repeat", minimum=1),
                _require_string(expected_key, "expected_observation_key"),
            )
        )
    capture_coverage = (
        sum(target in observed_keys for target in capture_targets)
        / len(capture_targets)
        if capture_targets
        else None
    )
    effective = [item for item in results if item.fault_injection_effective is True]
    detected = [item for item in effective if item.detected_fault is True]
    detector_claims = [item for item in results if item.detected_fault is True]
    false_detector_claims = [
        item for item in detector_claims if item.fault_injection_effective is not True
    ]
    diagnostic_gains = tuple(
        item.without_statewake_seconds - item.with_statewake_seconds
        for item in assessments
        if item.without_statewake_correct and item.with_statewake_correct
    )
    wall = tuple(item.wall_ms for item in measurements)
    metrics = CampaignMetrics(
        scenario_runs=len(results),
        passed_runs=sum(item.status == "PASS" for item in results),
        blocked_runs=sum(item.status == "BLOCKED_ENV" for item in results),
        capture_coverage=capture_coverage,
        evidence_completeness=(
            observed_required / expected_required if expected_required else None
        ),
        fault_recall=(len(detected) / len(effective) if effective else None),
        fault_precision=(
            (len(detector_claims) - len(false_detector_claims)) / len(detector_claims)
            if detector_claims
            else None
        ),
        false_assurance_count=sum(
            bool(item.forbidden_observations_seen) for item in results
        ),
        reconstructability=(
            sum(item.reconstructable for item in results) / len(results)
            if results
            else None
        ),
        diagnostic_gain_seconds_median=(
            statistics.median(diagnostic_gains) if diagnostic_gains else None
        ),
        wall_ms_p50=_percentile(wall, 0.50),
        wall_ms_p95=_percentile(wall, 0.95),
        wall_ms_p99=_percentile(wall, 0.99),
        privacy_leakage_count=_privacy_leakage_count(evidence_root),
    )
    return metrics, scenarios, results


def _metric(value: float | None) -> str:
    """Render an optional ratio or measurement."""
    return "NOT_MEASURED" if value is None else f"{value:.4f}"


def write_reports(
    input_root: Path, evidence_root: Path, reports_root: Path
) -> CampaignMetrics:
    """Render the five reports required by the real-system validation plan."""
    metrics, scenarios, results = analyze_campaign(input_root, evidence_root)
    reports_root.mkdir(parents=True, exist_ok=True)
    result_by_scenario: dict[str, list[ScenarioRunResult]] = {}
    for result in results:
        result_by_scenario.setdefault(result.scenario_id, []).append(result)

    summary_lines = [
        "# StateWake Real-System Validation Report",
        "",
        "This report is generated from independent host-truth records, StateWake observations, and harness results. It does not treat StateWake's own output as the oracle.",
        "",
        f"- Scenario runs: {metrics.scenario_runs}",
        f"- Passed runs: {metrics.passed_runs}",
        f"- Blocked runs: {metrics.blocked_runs}",
        f"- Capture coverage: {_metric(metrics.capture_coverage)}",
        f"- Evidence completeness: {_metric(metrics.evidence_completeness)}",
        f"- Fault recall: {_metric(metrics.fault_recall)}",
        f"- Fault precision: {_metric(metrics.fault_precision)}",
        f"- False-assurance count: {metrics.false_assurance_count}",
        f"- Reconstructability: {_metric(metrics.reconstructability)}",
        f"- Privacy leakage count: {metrics.privacy_leakage_count}",
        "",
        "## Scenario outcomes",
        "",
    ]
    for scenario in scenarios:
        runs = result_by_scenario.get(scenario.scenario_id, [])
        summary_lines.append(
            f"- `{scenario.scenario_id}`: "
            + ", ".join(f"repeat {item.repeat}={item.status}" for item in runs)
        )
    summary_lines.extend(
        [
            "",
            "## Boundary",
            "",
            "PASS means the scenario contract was met for the recorded observations. It does not mean the external system was factually correct, universally safe, or production-authorized.",
            "",
        ]
    )
    (reports_root / "REAL_SYSTEM_VALIDATION_REPORT.md").write_text(
        "\n".join(summary_lines), encoding="utf-8"
    )

    with (reports_root / "COVERAGE_MATRIX.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "scenario_id",
                "repeat",
                "status",
                "fault_injection_effective",
                "detected_fault",
                "required_missing",
                "forbidden_seen",
                "reconstructable",
            ]
        )
        for item in results:
            writer.writerow(
                [
                    item.scenario_id,
                    item.repeat,
                    item.status,
                    item.fault_injection_effective,
                    item.detected_fault,
                    ";".join(item.required_observations_missing),
                    ";".join(item.forbidden_observations_seen),
                    item.reconstructable,
                ]
            )

    defects = [
        item
        for item in results
        if item.status not in {"PASS", "NOT_APPLICABLE"}
        or item.forbidden_observations_seen
    ]
    defect_lines = ["# StateWake Real-System Validation Defect Register", ""]
    if not defects:
        defect_lines.append("No defects were recorded by the executed scenario set.")
    else:
        for item in defects:
            defect_lines.extend(
                [
                    f"## {item.scenario_id} / repeat {item.repeat}",
                    "",
                    f"- Status: `{item.status}`",
                    f"- Missing required observations: {', '.join(item.required_observations_missing) or 'none'}",
                    f"- Forbidden observations: {', '.join(item.forbidden_observations_seen) or 'none'}",
                    f"- Notes: {'; '.join(item.notes) or 'none'}",
                    "",
                ]
            )
    (reports_root / "DEFECT_REGISTER.md").write_text(
        "\n".join(defect_lines) + "\n", encoding="utf-8"
    )

    manifest = json.loads(
        (input_root / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    repro = [
        "# StateWake Real-System Validation Reproducibility Report",
        "",
        f"- Dataset digest: `{manifest['dataset_digest']}`",
        f"- Python: `{sys.version.split()[0]}`",
        f"- Platform: `{sys.platform}`",
        "- Offline mode: true",
        f"- Scenario definitions: {len(scenarios)}",
        "",
        "All generated trial outputs live outside the StateWake release workspace. External-host qualification requires immutable upstream revisions and result envelopes produced by those host trials.",
        "",
    ]
    (reports_root / "REPRODUCIBILITY_REPORT.md").write_text(
        "\n".join(repro), encoding="utf-8"
    )

    value_lines = [
        "# StateWake Value Assessment",
        "",
        "This assessment reports measurements; it does not convert missing measurements into positive claims.",
        "",
        f"- Diagnostic gain median (seconds): {_metric(metrics.diagnostic_gain_seconds_median)}",
        f"- Wall time p50 (ms): {_metric(metrics.wall_ms_p50)}",
        f"- Wall time p95 (ms): {_metric(metrics.wall_ms_p95)}",
        f"- Wall time p99 (ms): {_metric(metrics.wall_ms_p99)}",
        f"- Fault recall: {_metric(metrics.fault_recall)}",
        f"- Fault precision: {_metric(metrics.fault_precision)}",
        f"- Reconstructability: {_metric(metrics.reconstructability)}",
        "",
        "Human timing remains NOT_MEASURED until operator-assessments.jsonl is supplied with paired observations.",
        "",
    ]
    (reports_root / "VALUE_ASSESSMENT.md").write_text(
        "\n".join(value_lines), encoding="utf-8"
    )
    return metrics


def _print(payload: object) -> None:
    """Print one stable machine-readable CLI result."""
    print(json.dumps(payload, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    """Run the system-trial harness command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    generate = subparsers.add_parser(
        "generate", help="generate deterministic local-control datasets"
    )
    generate.add_argument("--seed", type=int, required=True)
    generate.add_argument("--output", type=Path, required=True)

    validate = subparsers.add_parser(
        "validate-datasets", help="validate frozen trial datasets"
    )
    validate.add_argument("--input", type=Path, required=True)

    run = subparsers.add_parser(
        "run", help="execute local controls and/or imported external results"
    )
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--workspaces", type=Path, required=True)
    run.add_argument("--evidence", type=Path, required=True)
    run.add_argument("--offline", action="store_true")

    analyze = subparsers.add_parser("analyze", help="analyze recorded trial evidence")
    analyze.add_argument("--input", type=Path, required=True)
    analyze.add_argument("--evidence", type=Path, required=True)
    analyze.add_argument("--reports", type=Path, required=True)

    native = subparsers.add_parser(
        "qualify-native-hosts",
        help="run real native-SDK qualification plus independent-oracle local host exercises",
    )
    native.add_argument("--workspaces", type=Path, required=True)
    native.add_argument("--evidence", type=Path, required=True)
    native.add_argument("--timeout", type=int, default=180)

    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            scenarios = generate_datasets(args.output, seed=args.seed)
            _print({"status": "PASS", "scenario_count": len(scenarios)})
            return 0
        if args.command == "validate-datasets":
            scenarios = validate_datasets(args.input)
            _print({"status": "PASS", "scenario_count": len(scenarios)})
            return 0
        if args.command == "run":
            results = run_campaign(
                args.input,
                args.workspaces,
                args.evidence,
                offline=bool(args.offline),
            )
            overall = (
                "PASS"
                if all(item.status == "PASS" for item in results)
                else (
                    "BLOCKED_ENV"
                    if all(item.status in {"PASS", "BLOCKED_ENV"} for item in results)
                    else "FAIL"
                )
            )
            _print({"status": overall, "runs": [asdict(item) for item in results]})
            return 0 if overall == "PASS" else (2 if overall == "BLOCKED_ENV" else 1)
        if args.command == "qualify-native-hosts":
            from scripts.testing.native_host_qualification import (
                run_native_host_qualification,
            )

            summary = run_native_host_qualification(
                evidence_root=args.evidence,
                workspaces_root=args.workspaces,
                timeout=args.timeout,
            )
            _print(summary)
            status = summary.get("status")
            return 0 if status == "PASS" else (2 if status == "BLOCKED_ENV" else 1)
        metrics = write_reports(args.input, args.evidence, args.reports)
        _print({"status": "PASS", "metrics": asdict(metrics)})
        return 0
    except (OSError, TrialContractError, json.JSONDecodeError) as exc:
        _print({"status": "FAIL", "error": str(exc)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
