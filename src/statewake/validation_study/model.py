"""Deterministic comparative validation study data model."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Literal

BaselineMode = Literal[
    "final_output_only",
    "conventional_logs",
    "structured_traces",
    "statewake_full",
]
WorkloadKind = Literal[
    "rag_answer",
    "tool_action",
    "incident_recovery",
    "release_verification",
    "human_approval_workflow",
]
FaultKind = Literal[
    "omitted_evidence",
    "malformed_evidence",
    "stale_corpus",
    "wrong_model_version",
    "changed_prompt_template",
    "missing_tool_authorization",
    "modified_tool_output",
    "broken_provenance_edge",
    "invalid_reliability_transition",
    "partial_workspace_write",
    "recovery_without_preserved_failure",
    "unsigned_release_artifact",
]


def canonical_digest(payload: Mapping[str, object]) -> str:
    """Return a deterministic SHA-256 digest for a JSON-compatible payload."""
    encoded = json.dumps(
        dict(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ValidationBaseline:
    """One comparison baseline used in the Phase 7 study."""

    mode: BaselineMode
    captured_properties: tuple[str, ...]
    limitation: str

    def to_dict(self) -> dict[str, object]:
        """Serialize the baseline descriptor."""
        return {
            "mode": self.mode,
            "captured_properties": list(self.captured_properties),
            "limitation": self.limitation,
        }


@dataclass(frozen=True, slots=True)
class FaultInjection:
    """One deterministic fault injected into a representative workload."""

    kind: FaultKind
    description: str
    affected_property: str

    def to_dict(self) -> dict[str, object]:
        """Serialize the fault descriptor."""
        return {
            "kind": self.kind,
            "description": self.description,
            "affected_property": self.affected_property,
        }


@dataclass(frozen=True, slots=True)
class WorkloadDefinition:
    """One representative AI-system workload used for comparison."""

    workload: WorkloadKind
    profile_id: str
    target_properties: tuple[str, ...]
    required_ai_contracts: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Serialize the workload descriptor."""
        return {
            "workload": self.workload,
            "profile_id": self.profile_id,
            "target_properties": list(self.target_properties),
            "required_ai_contracts": list(self.required_ai_contracts),
        }


@dataclass(frozen=True, slots=True)
class ValidationCaseResult:
    """Observed result for one workload, baseline, and fault set."""

    workload: WorkloadKind
    baseline: BaselineMode
    injected_faults: tuple[FaultKind, ...]
    target_properties: tuple[str, ...]
    checkable_properties: tuple[str, ...]
    detected_faults: tuple[FaultKind, ...]
    false_positive: bool
    profile_satisfied: bool | None
    notes: tuple[str, ...]

    @property
    def missing_properties(self) -> tuple[str, ...]:
        """Return target properties not independently checkable by this baseline."""
        checkable = set(self.checkable_properties)
        return tuple(item for item in self.target_properties if item not in checkable)

    def to_dict(self) -> dict[str, object]:
        """Serialize the case result."""
        return {
            "workload": self.workload,
            "baseline": self.baseline,
            "injected_faults": list(self.injected_faults),
            "target_properties": list(self.target_properties),
            "checkable_properties": list(self.checkable_properties),
            "missing_properties": list(self.missing_properties),
            "detected_faults": list(self.detected_faults),
            "false_positive": self.false_positive,
            "profile_satisfied": self.profile_satisfied,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class StudyMetrics:
    """Aggregate metrics for one baseline across deterministic Phase 7 cases."""

    baseline: BaselineMode
    case_count: int
    injected_fault_count: int
    detected_fault_count: int
    valid_case_count: int
    false_positive_count: int
    target_property_count: int
    checkable_property_count: int

    @property
    def verification_coverage(self) -> float:
        """Return independently checkable target properties divided by targets."""
        if self.target_property_count == 0:
            return 0.0
        return self.checkable_property_count / self.target_property_count

    @property
    def fault_detection_rate(self) -> float:
        """Return detected injected faults divided by injected faults."""
        if self.injected_fault_count == 0:
            return 0.0
        return self.detected_fault_count / self.injected_fault_count

    @property
    def false_positive_rate(self) -> float:
        """Return valid cases rejected divided by valid cases."""
        if self.valid_case_count == 0:
            return 0.0
        return self.false_positive_count / self.valid_case_count

    def to_dict(self) -> dict[str, object]:
        """Serialize aggregate metrics."""
        return {
            "baseline": self.baseline,
            "case_count": self.case_count,
            "injected_fault_count": self.injected_fault_count,
            "detected_fault_count": self.detected_fault_count,
            "valid_case_count": self.valid_case_count,
            "false_positive_count": self.false_positive_count,
            "target_property_count": self.target_property_count,
            "checkable_property_count": self.checkable_property_count,
            "verification_coverage": self.verification_coverage,
            "fault_detection_rate": self.fault_detection_rate,
            "false_positive_rate": self.false_positive_rate,
        }


@dataclass(frozen=True, slots=True)
class ComparativeValidationStudy:
    """Deterministic Phase 7 comparative validation study result."""

    study_id: str
    baselines: tuple[ValidationBaseline, ...]
    workloads: tuple[WorkloadDefinition, ...]
    faults: tuple[FaultInjection, ...]
    cases: tuple[ValidationCaseResult, ...]
    metrics: tuple[StudyMetrics, ...]
    limitations: tuple[str, ...]

    @property
    def digest(self) -> str:
        """Return deterministic digest for the complete study result."""
        return canonical_digest(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        """Serialize the study result."""
        return {
            "study_id": self.study_id,
            "baselines": [item.to_dict() for item in self.baselines],
            "workloads": [item.to_dict() for item in self.workloads],
            "faults": [item.to_dict() for item in self.faults],
            "cases": [item.to_dict() for item in self.cases],
            "metrics": [item.to_dict() for item in self.metrics],
            "limitations": list(self.limitations),
        }


def sequence_tuple(values: Sequence[str]) -> tuple[str, ...]:
    """Return a stable tuple of non-empty strings preserving input order."""
    result: list[str] = []
    for value in values:
        if not value.strip():
            raise ValueError("validation study sequences must not contain blanks.")
        result.append(value)
    return tuple(result)
