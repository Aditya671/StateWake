"""Report rendering, persistence, and loading for comparative validation studies."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import cast

from statewake.services.persistence import atomic_write_text
from statewake.validation_study.model import (
    BaselineMode,
    ComparativeValidationStudy,
    FaultInjection,
    FaultKind,
    StudyMetrics,
    ValidationBaseline,
    ValidationCaseResult,
    WorkloadDefinition,
    WorkloadKind,
)


def render_study_json(study: ComparativeValidationStudy) -> str:
    """Render a deterministic JSON study report."""
    payload = {**study.to_dict(), "digest": study.digest}
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_study_markdown(study: ComparativeValidationStudy) -> str:
    """Render a deterministic Markdown study report."""
    lines = [
        "# StateWake Comparative Validation Study",
        "",
        f"**Study ID:** `{study.study_id}`",
        f"**Digest:** `{study.digest}`",
        "",
        "## Metrics",
        "",
        "| Baseline | Coverage | Detection | False positives | Cases |",
        "|---|---:|---:|---:|---:|",
    ]
    for metric in study.metrics:
        lines.append(
            "| "
            f"{metric.baseline} | "
            f"{metric.verification_coverage:.3f} | "
            f"{metric.fault_detection_rate:.3f} | "
            f"{metric.false_positive_rate:.3f} | "
            f"{metric.case_count} |"
        )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in study.limitations)
    lines.extend(["", "## Cases", ""])
    for case in study.cases:
        fault_text = ", ".join(case.injected_faults) if case.injected_faults else "none"
        detected_text = (
            ", ".join(case.detected_faults) if case.detected_faults else "none"
        )
        lines.extend(
            [
                f"### {case.workload} / {case.baseline}",
                "",
                f"- Injected faults: {fault_text}",
                f"- Detected faults: {detected_text}",
                f"- Checkable properties: {len(case.checkable_properties)} / "
                f"{len(case.target_properties)}",
                f"- Profile satisfied: {case.profile_satisfied}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def write_study_reports(
    study: ComparativeValidationStudy,
    directory: Path,
) -> tuple[Path, Path]:
    """Write JSON and Markdown study reports to a directory."""
    directory.mkdir(parents=True, exist_ok=True)
    json_path = directory / f"{study.study_id}.json"
    markdown_path = directory / f"{study.study_id}.md"
    atomic_write_text(json_path, render_study_json(study))
    atomic_write_text(markdown_path, render_study_markdown(study))
    return json_path, markdown_path


def load_study_report(
    path: Path, *, max_bytes: int = 8_388_608
) -> ComparativeValidationStudy:
    """Load and strictly validate one frozen comparative-study JSON artifact."""
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("rb") as handle:
        encoded = handle.read(max_bytes + 1)
    if len(encoded) > max_bytes:
        raise OverflowError("validation study exceeds configured read limit")
    try:
        raw_payload = json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("validation study must be valid UTF-8 JSON") from exc
    if not isinstance(raw_payload, dict) or any(
        not isinstance(key, str) for key in raw_payload
    ):
        raise ValueError("validation study root must be an object")
    payload = cast(dict[str, object], raw_payload)

    def objects(name: str) -> list[dict[str, object]]:
        """Return one validated array of JSON objects from the study payload."""
        value = payload.get(name)
        if not isinstance(value, list):
            raise ValueError(f"validation study {name} must be an array of objects")
        result: list[dict[str, object]] = []
        for item in value:
            if not isinstance(item, dict) or any(
                not isinstance(key, str) for key in item
            ):
                raise ValueError(f"validation study {name} must be an array of objects")
            result.append(cast(dict[str, object], item))
        return result

    def text(item: dict[str, object], name: str) -> str:
        """Return a required non-blank string field without coercion."""
        value = item.get(name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"validation study {name} must be a non-blank string")
        return value

    def strings(item: dict[str, object], name: str) -> tuple[str, ...]:
        """Return a required array of non-blank strings without coercion."""
        value = item.get(name)
        if not isinstance(value, list):
            raise ValueError(f"validation study {name} must be an array of strings")
        result: list[str] = []
        for entry in value:
            if not isinstance(entry, str) or not entry.strip():
                raise ValueError(
                    f"validation study {name} must contain non-blank strings"
                )
            result.append(entry)
        return tuple(result)

    def integer(item: dict[str, object], name: str) -> int:
        """Return a required non-negative integer field without coercion."""
        value = item.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"validation study {name} must be a non-negative integer")
        return value

    def boolean(item: dict[str, object], name: str) -> bool:
        """Return a required boolean field without truthiness coercion."""
        value = item.get(name)
        if not isinstance(value, bool):
            raise ValueError(f"validation study {name} must be a boolean")
        return value

    def optional_boolean(item: dict[str, object], name: str) -> bool | None:
        """Return an explicit boolean-or-null field without coercion."""
        value = item.get(name)
        if value is not None and not isinstance(value, bool):
            raise ValueError(f"validation study {name} must be boolean or null")
        return value

    study_id_value = payload.get("study_id")
    if not isinstance(study_id_value, str) or not study_id_value.strip():
        raise ValueError("validation study study_id must be a non-blank string")

    baselines = tuple(
        ValidationBaseline(
            mode=cast(BaselineMode, text(item, "mode")),
            captured_properties=strings(item, "captured_properties"),
            limitation=text(item, "limitation"),
        )
        for item in objects("baselines")
    )
    workloads = tuple(
        WorkloadDefinition(
            workload=cast(WorkloadKind, text(item, "workload")),
            profile_id=text(item, "profile_id"),
            target_properties=strings(item, "target_properties"),
            required_ai_contracts=strings(item, "required_ai_contracts"),
        )
        for item in objects("workloads")
    )
    faults = tuple(
        FaultInjection(
            kind=cast(FaultKind, text(item, "kind")),
            description=text(item, "description"),
            affected_property=text(item, "affected_property"),
        )
        for item in objects("faults")
    )

    cases_list: list[ValidationCaseResult] = []
    for item in objects("cases"):
        target_properties = strings(item, "target_properties")
        checkable_properties = strings(item, "checkable_properties")
        case = ValidationCaseResult(
            workload=cast(WorkloadKind, text(item, "workload")),
            baseline=cast(BaselineMode, text(item, "baseline")),
            injected_faults=tuple(
                cast(FaultKind, value) for value in strings(item, "injected_faults")
            ),
            target_properties=target_properties,
            checkable_properties=checkable_properties,
            detected_faults=tuple(
                cast(FaultKind, value) for value in strings(item, "detected_faults")
            ),
            false_positive=boolean(item, "false_positive"),
            profile_satisfied=optional_boolean(item, "profile_satisfied"),
            notes=strings(item, "notes"),
        )
        if "missing_properties" in item:
            recorded_missing = strings(item, "missing_properties")
            if recorded_missing != case.missing_properties:
                raise ValueError(
                    "validation study case missing_properties is inconsistent"
                )
        cases_list.append(case)
    cases = tuple(cases_list)

    metrics = tuple(
        StudyMetrics(
            baseline=cast(BaselineMode, text(item, "baseline")),
            case_count=integer(item, "case_count"),
            injected_fault_count=integer(item, "injected_fault_count"),
            detected_fault_count=integer(item, "detected_fault_count"),
            valid_case_count=integer(item, "valid_case_count"),
            false_positive_count=integer(item, "false_positive_count"),
            target_property_count=integer(item, "target_property_count"),
            checkable_property_count=integer(item, "checkable_property_count"),
        )
        for item in objects("metrics")
    )
    limitations_raw = payload.get("limitations")
    if not isinstance(limitations_raw, list):
        raise ValueError("validation study limitations must be an array")
    limitations: list[str] = []
    for item in limitations_raw:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(
                "validation study limitations must contain non-blank strings"
            )
        limitations.append(item)

    study = ComparativeValidationStudy(
        study_id=study_id_value,
        baselines=baselines,
        workloads=workloads,
        faults=faults,
        cases=cases,
        metrics=metrics,
        limitations=tuple(limitations),
    )
    supplied_digest = payload.get("digest")
    if not isinstance(supplied_digest, str) or not supplied_digest:
        raise ValueError("validation study digest is required")
    if supplied_digest != study.digest:
        raise ValueError("validation study digest mismatch")
    _validate_study_consistency(study)
    return study


def _validate_study_consistency(study: ComparativeValidationStudy) -> None:
    """Reject inconsistent denominators, unsupported identities, and empty study inputs."""
    allowed_baselines = {
        "final_output_only",
        "conventional_logs",
        "structured_traces",
        "statewake_full",
    }
    allowed_workloads = {
        "rag_answer",
        "tool_action",
        "incident_recovery",
        "release_verification",
        "human_approval_workflow",
    }
    allowed_faults = {
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
    }
    if (
        not study.study_id.strip()
        or not study.baselines
        or not study.workloads
        or not study.metrics
    ):
        raise ValueError("validation study is incomplete")
    if any(item.mode not in allowed_baselines for item in study.baselines):
        raise ValueError("validation study contains an unsupported baseline")
    if any(item.workload not in allowed_workloads for item in study.workloads):
        raise ValueError("validation study contains an unsupported workload")
    if any(item.kind not in allowed_faults for item in study.faults):
        raise ValueError("validation study contains an unsupported fault")
    if any(
        case.baseline not in allowed_baselines or case.workload not in allowed_workloads
        for case in study.cases
    ):
        raise ValueError("validation study case identity is unsupported")
    if any(
        fault not in allowed_faults
        for case in study.cases
        for fault in (*case.injected_faults, *case.detected_faults)
    ):
        raise ValueError("validation study case contains an unsupported fault")

    for metric in study.metrics:
        group = [case for case in study.cases if case.baseline == metric.baseline]
        if metric.case_count != len(group):
            raise ValueError("validation study metric case_count is inconsistent")
        if metric.injected_fault_count != sum(
            len(case.injected_faults) for case in group
        ):
            raise ValueError(
                "validation study injected-fault denominator is inconsistent"
            )
        if metric.detected_fault_count != sum(
            len(case.detected_faults) for case in group
        ):
            raise ValueError(
                "validation study detected-fault numerator is inconsistent"
            )
        valid = [case for case in group if not case.injected_faults]
        if metric.valid_case_count != len(valid):
            raise ValueError("validation study valid-case denominator is inconsistent")
        if metric.false_positive_count != sum(case.false_positive for case in valid):
            raise ValueError(
                "validation study false-positive numerator is inconsistent"
            )
        if metric.target_property_count != sum(
            len(case.target_properties) for case in group
        ):
            raise ValueError(
                "validation study target-property denominator is inconsistent"
            )
        if metric.checkable_property_count != sum(
            len(case.checkable_properties) for case in group
        ):
            raise ValueError("validation study coverage numerator is inconsistent")


def report_timestamp(value: datetime) -> str:
    """Return an ISO timestamp for external report metadata."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("report timestamps must be timezone-aware.")
    return value.isoformat()
