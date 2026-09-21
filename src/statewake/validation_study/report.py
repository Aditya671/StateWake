"""Report rendering and persistence for Phase 7 validation studies."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from statewake.services.persistence import atomic_write_text
from statewake.validation_study.model import ComparativeValidationStudy


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


def report_timestamp(value: datetime) -> str:
    """Return an ISO timestamp for external report metadata."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("report timestamps must be timezone-aware.")
    return value.isoformat()
