"""Run frozen public-trial regressions and native-SDK qualification gates."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
import tomllib
from dataclasses import asdict, dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Final, Literal

PROJECT_ROOT: Final = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST: Final = (
    PROJECT_ROOT / "tests/fixtures/public_trial_regression_manifest.json"
)
PYPROJECT: Final = PROJECT_ROOT / "pyproject.toml"
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
QualificationStatus = Literal[
    "PASS", "FAIL_STATEWAKE", "FAIL_INTEGRATION", "BLOCKED_ENV", "NOT_APPLICABLE"
]
DependencyState = Literal["INSTALLED", "MISSING"]


@dataclass(frozen=True, slots=True)
class TrialCase:
    """One frozen public-repository regression and qualification case."""

    case_id: str
    anomaly: str
    repository: str
    commit: str
    source_tests: tuple[str, ...]
    qualification_tests: tuple[str, ...]
    requires_extra: str | None
    qualification_requires_sdk: bool
    expected: str


@dataclass(frozen=True, slots=True)
class DependencyEvidence:
    """One declared integration dependency and its installed state."""

    requirement: str
    distribution: str
    state: DependencyState
    installed_version: str | None


@dataclass(frozen=True, slots=True)
class PytestEvidence:
    """Bounded result of one isolated pytest subprocess."""

    status: Literal["PASS", "FAIL", "TIMEOUT"]
    returncode: int | None
    skipped: int
    collection_error: bool
    stdout: str
    stderr: str
    reason: str | None


def _optional_dependencies() -> dict[str, tuple[str, ...]]:
    """Return project optional-dependency declarations from the active repository."""
    payload = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    raw = payload.get("project", {}).get("optional-dependencies", {})
    if not isinstance(raw, dict):
        raise ValueError("pyproject optional-dependencies must be a table")
    parsed: dict[str, tuple[str, ...]] = {}
    for extra, requirements in raw.items():
        if not isinstance(extra, str) or not isinstance(requirements, list):
            raise ValueError("invalid optional dependency declaration")
        if not all(isinstance(item, str) and item.strip() for item in requirements):
            raise ValueError(f"{extra}: requirements must be non-empty strings")
        parsed[extra] = tuple(requirements)
    return parsed


def _distribution_name(requirement: str) -> str:
    """Extract the distribution identifier from one PEP 508 requirement string."""
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9_.-]*)", requirement)
    if match is None:
        raise ValueError(f"cannot parse requirement distribution: {requirement!r}")
    return match.group(1)


def _dependency_evidence(extra: str | None) -> tuple[DependencyEvidence, ...]:
    """Resolve installed evidence for the dependencies declared by one extra."""
    if extra is None:
        return ()
    optional = _optional_dependencies()
    requirements = optional.get(extra)
    if requirements is None:
        raise ValueError(f"unknown integration extra in manifest: {extra}")
    evidence: list[DependencyEvidence] = []
    for requirement in requirements:
        distribution = _distribution_name(requirement)
        try:
            version = importlib_metadata.version(distribution)
        except importlib_metadata.PackageNotFoundError:
            evidence.append(
                DependencyEvidence(requirement, distribution, "MISSING", None)
            )
        else:
            evidence.append(
                DependencyEvidence(requirement, distribution, "INSTALLED", version)
            )
    return tuple(evidence)


def _validated_tests(case_id: str, value: object, field: str) -> tuple[str, ...]:
    """Require existing pytest targets for one manifest case."""
    if not isinstance(value, list):
        raise ValueError(f"{case_id}: {field} must be an array of non-empty strings")
    targets = tuple(item for item in value if isinstance(item, str) and item)
    if len(targets) != len(value):
        raise ValueError(f"{case_id}: {field} must be an array of non-empty strings")
    for target in targets:
        file_part = target.split("::", 1)[0]
        if not (PROJECT_ROOT / file_part).is_file():
            raise ValueError(f"{case_id}: missing {field} target {file_part}")
    return targets


def load_manifest(path: Path) -> tuple[TrialCase, ...]:
    """Load and strictly validate the frozen public-trial regression manifest."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported public-trial regression manifest schema")
    if set(payload.get("outcomes", ())) != ALLOWED_OUTCOMES:
        raise ValueError("public-trial outcome vocabulary drift")
    optional = _optional_dependencies()
    cases: list[TrialCase] = []
    seen: set[str] = set()
    for raw in payload.get("cases", ()):
        if not isinstance(raw, dict):
            raise ValueError("public-trial case must be an object")
        case_id = raw.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError("case_id must be a unique non-empty string")
        seen.add(case_id)
        source_tests = _validated_tests(
            case_id, raw.get("source_tests"), "source_tests"
        )
        raw_qualification = raw.get("qualification_tests", [])
        qualification_tests = _validated_tests(
            case_id, raw_qualification, "qualification_tests"
        )
        commit = raw.get("commit")
        if not isinstance(commit, str) or len(commit) != 40:
            raise ValueError(
                f"{case_id}: pinned upstream commit must be a 40-character SHA"
            )
        requires_extra = raw.get("requires_extra")
        if requires_extra is not None:
            if not isinstance(requires_extra, str) or requires_extra not in optional:
                raise ValueError(
                    f"{case_id}: unknown requires_extra {requires_extra!r}"
                )
        requires_sdk = bool(raw.get("qualification_requires_sdk"))
        if requires_sdk and requires_extra is None:
            raise ValueError(
                f"{case_id}: SDK qualification requires an integration extra"
            )
        if requires_sdk and not qualification_tests:
            raise ValueError(
                f"{case_id}: SDK qualification requires qualification_tests"
            )
        if not requires_sdk and qualification_tests:
            raise ValueError(
                f"{case_id}: qualification_tests require qualification_requires_sdk"
            )
        cases.append(
            TrialCase(
                case_id=case_id,
                anomaly=str(raw.get("anomaly")),
                repository=str(raw.get("repository")),
                commit=commit,
                source_tests=source_tests,
                qualification_tests=qualification_tests,
                requires_extra=requires_extra,
                qualification_requires_sdk=requires_sdk,
                expected=str(raw.get("expected")),
            )
        )
    if not cases:
        raise ValueError("public-trial regression manifest has no cases")
    return tuple(cases)


def _skip_count(output: str) -> int:
    """Return pytest's aggregate skipped-test count from bounded output."""
    matches = re.findall(r"(?P<count>\d+) skipped", output)
    return max((int(value) for value in matches), default=0)


def _run_pytest(targets: tuple[str, ...], timeout: int) -> PytestEvidence:
    """Run pytest in an isolated subprocess and retain bounded evidence."""
    command = [sys.executable, "-m", "pytest", "-q", "-ra", *targets]
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return PytestEvidence(
            status="TIMEOUT",
            returncode=None,
            skipped=0,
            collection_error=False,
            stdout=(exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            stderr=(exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            reason=f"pytest timed out after {timeout}s",
        )
    output = completed.stdout + "\n" + completed.stderr
    collection_error = "ERROR collecting" in output or "Interrupted:" in output
    return PytestEvidence(
        status="PASS" if completed.returncode == 0 and not collection_error else "FAIL",
        returncode=completed.returncode,
        skipped=_skip_count(output),
        collection_error=collection_error,
        stdout=completed.stdout[-4000:],
        stderr=completed.stderr[-4000:],
        reason=None
        if completed.returncode == 0 and not collection_error
        else "pytest failed",
    )


def _qualification_status(
    case: TrialCase,
    *,
    dependencies: tuple[DependencyEvidence, ...],
    qualification: PytestEvidence | None,
) -> tuple[QualificationStatus, str | None]:
    """Classify native qualification without promoting absence into success."""
    if not case.qualification_requires_sdk:
        return "PASS", None
    missing = tuple(
        item.distribution for item in dependencies if item.state == "MISSING"
    )
    if missing:
        return "BLOCKED_ENV", "missing installed SDK distribution(s): " + ", ".join(
            missing
        )
    if qualification is None:
        return "NOT_APPLICABLE", "native qualification was not executed"
    if qualification.status == "TIMEOUT":
        return "FAIL_INTEGRATION", qualification.reason
    if qualification.collection_error:
        return (
            "FAIL_INTEGRATION",
            "installed SDK could not collect its native qualification probe",
        )
    if qualification.status == "FAIL":
        return "FAIL_STATEWAKE", "native SDK qualification assertion failed"
    if qualification.skipped:
        return (
            "FAIL_INTEGRATION",
            "SDK distribution is installed but a required native qualification probe skipped",
        )
    return "PASS", None


def _run_case(case: TrialCase, timeout: int, mode: str) -> dict[str, object]:
    dependencies = _dependency_evidence(case.requires_extra)
    source = _run_pytest(case.source_tests, timeout)
    qualification: PytestEvidence | None = None
    if (
        mode == "qualification"
        and source.status == "PASS"
        and case.qualification_requires_sdk
        and all(item.state == "INSTALLED" for item in dependencies)
    ):
        qualification = _run_pytest(case.qualification_tests, timeout)

    qualification_status, qualification_reason = _qualification_status(
        case, dependencies=dependencies, qualification=qualification
    )
    if source.status != "PASS":
        status = "FAIL_STATEWAKE"
        reason = source.reason or "source regression failed"
    elif mode == "source":
        status = "PASS"
        reason = None
    elif qualification_status == "PASS":
        status = "PASS"
        reason = None
    elif qualification_status == "BLOCKED_ENV":
        status = "BLOCKED_ENV"
        reason = qualification_reason
    elif qualification_status == "FAIL_INTEGRATION":
        status = "FAIL_INTEGRATION"
        reason = qualification_reason
    elif qualification_status == "FAIL_STATEWAKE":
        status = "FAIL_STATEWAKE"
        reason = qualification_reason
    else:
        status = "FAIL_INTEGRATION"
        reason = qualification_reason or "required native qualification did not execute"

    return {
        "case_id": case.case_id,
        "anomaly": case.anomaly,
        "repository": case.repository,
        "commit": case.commit,
        "status": status,
        "qualification_status": qualification_status,
        "qualification_reason": qualification_reason,
        "requires_extra": case.requires_extra,
        "qualification_requires_sdk": case.qualification_requires_sdk,
        "dependencies": [asdict(item) for item in dependencies],
        "expected": case.expected,
        "reason": reason,
        "source": asdict(source),
        "qualification": asdict(qualification) if qualification is not None else None,
        # Retain the legacy bounded source fields for existing evidence consumers.
        "skipped": source.skipped,
        "returncode": source.returncode,
        "stdout": source.stdout,
        "stderr": source.stderr,
    }


def _overall_status(results: list[dict[str, object]]) -> str:
    statuses = {str(result["status"]) for result in results}
    if statuses <= {"PASS"}:
        return "PASS"
    if statuses <= {"PASS", "BLOCKED_ENV"}:
        return "BLOCKED_ENV"
    return "FAIL"


def _render_report(record: dict[str, object]) -> str:
    """Render bounded human-readable native qualification evidence."""
    results = record["results"]
    assert isinstance(results, list)
    lines = [
        "# StateWake Native Integration Qualification Report",
        "",
        f"- Mode: `{record['mode']}`",
        f"- Overall status: **{record['status']}**",
        f"- Python: `{record['python_version']}`",
        f"- Executable: `{record['python_executable']}`",
        "- Publication authorized: **No**",
        "",
        "| Case | Status | Native qualification | SDK evidence |",
        "| --- | --- | --- | --- |",
    ]
    for raw in results:
        assert isinstance(raw, dict)
        dependencies = raw.get("dependencies", [])
        dep_texts: list[str] = []
        if isinstance(dependencies, list):
            for dep in dependencies:
                if not isinstance(dep, dict):
                    continue
                version = dep.get("installed_version") or "missing"
                dep_texts.append(f"{dep.get('distribution')}={version}")
        lines.append(
            "| "
            + " | ".join(
                (
                    f"`{raw.get('case_id')}`",
                    str(raw.get("status")),
                    str(raw.get("qualification_status")),
                    ", ".join(dep_texts) if dep_texts else "not required",
                )
            )
            + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Source-mode PASS proves only the frozen StateWake regression targets. In qualification mode, a native SDK case is PASS only when its declared distribution is installed and every dedicated real-SDK probe executes without skips. Missing distributions are BLOCKED_ENV. An installed SDK whose probe cannot collect, skips, or times out is FAIL_INTEGRATION. A native assertion failure is FAIL_STATEWAKE.",
            "",
            "The native probes are credential-free and must not call paid/live model services. This report does not authorize publication and does not prove correctness of the external framework itself.",
            "",
        ]
    )
    return "\n".join(lines)


def run_matrix(
    *,
    manifest: Path = DEFAULT_MANIFEST,
    timeout: int = 180,
    mode: Literal["source", "qualification"] = "source",
) -> dict[str, object]:
    """Return one structured source/native qualification record.

    This is the single programmatic authority used by both the standalone CLI
    and the independent-oracle system-trial harness. It deliberately executes
    the same manifest cases and classification logic as the CLI rather than
    creating a second native qualification runner.
    """
    cases = load_manifest(manifest)
    results = [_run_case(case, timeout, mode) for case in cases]
    return {
        "workflow": "statewake-public-trial-regressions",
        "mode": mode,
        "manifest": str(manifest),
        "status": _overall_status(results),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "results": results,
        "publication_authorized": False,
    }


def main() -> int:
    """Execute the frozen source-side or real native-SDK qualification matrix."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--mode", choices=("source", "qualification"), default="source")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    cases = load_manifest(args.manifest)
    if args.list:
        print(json.dumps({"cases": [c.case_id for c in cases]}, sort_keys=True))
        return 0
    record = run_matrix(manifest=args.manifest, timeout=args.timeout, mode=args.mode)
    if args.output:
        path = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if args.report:
        path = args.report if args.report.is_absolute() else PROJECT_ROOT / args.report
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_render_report(record), encoding="utf-8")
    print(json.dumps(record, sort_keys=True))
    if record["status"] == "PASS":
        return 0
    return 2 if record["status"] == "BLOCKED_ENV" else 1


if __name__ == "__main__":
    raise SystemExit(main())
