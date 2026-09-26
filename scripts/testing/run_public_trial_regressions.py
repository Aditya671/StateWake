"""Run source regressions derived from the frozen public-repository trial."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final

PROJECT_ROOT: Final = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST: Final = (
    PROJECT_ROOT / "tests/fixtures/public_trial_regression_manifest.json"
)
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


@dataclass(frozen=True, slots=True)
class TrialCase:
    """TrailCase Dataclass."""

    case_id: str
    anomaly: str
    repository: str
    commit: str
    source_tests: tuple[str, ...]
    requires_extra: str | None
    qualification_requires_sdk: bool
    expected: str


def load_manifest(path: Path) -> tuple[TrialCase, ...]:
    """Load and strictly validate the frozen public-trial regression manifest."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported public-trial regression manifest schema")
    if set(payload.get("outcomes", ())) != ALLOWED_OUTCOMES:
        raise ValueError("public-trial outcome vocabulary drift")
    cases: list[TrialCase] = []
    seen: set[str] = set()
    for raw in payload.get("cases", ()):
        case_id = raw.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in seen:
            raise ValueError("case_id must be a unique non-empty string")
        seen.add(case_id)
        tests = raw.get("source_tests")
        if (
            not isinstance(tests, list)
            or not tests
            or not all(isinstance(x, str) and x for x in tests)
        ):
            raise ValueError(f"{case_id}: source_tests must be non-empty strings")
        for target in tests:
            file_part = target.split("::", 1)[0]
            if not (PROJECT_ROOT / file_part).is_file():
                raise ValueError(
                    f"{case_id}: missing source regression target {file_part}"
                )
        commit = raw.get("commit")
        if not isinstance(commit, str) or len(commit) != 40:
            raise ValueError(
                f"{case_id}: pinned upstream commit must be a 40-character SHA"
            )
        cases.append(
            TrialCase(
                case_id,
                str(raw.get("anomaly")),
                str(raw.get("repository")),
                commit,
                tuple(tests),
                raw.get("requires_extra"),
                bool(raw.get("qualification_requires_sdk")),
                str(raw.get("expected")),
            )
        )
    if not cases:
        raise ValueError("public-trial regression manifest has no cases")
    return tuple(cases)


def _run_case(case: TrialCase, timeout: int, mode: str) -> dict[str, object]:
    command = [sys.executable, "-m", "pytest", "-q", "-ra", *case.source_tests]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    output = completed.stdout + "\n" + completed.stderr
    collection_error = "ERROR collecting" in output or "Interrupted:" in output
    match = re.search(r"(?P<count>\d+) skipped", output)
    skipped = int(match.group("count")) if match else 0
    if completed.returncode != 0 or collection_error:
        status = "FAIL_STATEWAKE"
    elif mode == "qualification" and case.qualification_requires_sdk and skipped:
        status = "BLOCKED_ENV"
    else:
        status = "PASS"
    qualification_status = (
        "BLOCKED_ENV" if case.qualification_requires_sdk and skipped else "PASS"
    )
    return {
        "case_id": case.case_id,
        "anomaly": case.anomaly,
        "repository": case.repository,
        "commit": case.commit,
        "status": status,
        "qualification_status": qualification_status,
        "skipped": skipped,
        "returncode": completed.returncode,
        "requires_extra": case.requires_extra,
        "qualification_requires_sdk": case.qualification_requires_sdk,
        "expected": case.expected,
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


def main() -> int:
    """Execute the frozen source-side public-trial regression matrix."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--mode", choices=("source", "qualification"), default="source")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    cases = load_manifest(args.manifest)
    if args.list:
        print(json.dumps({"cases": [c.case_id for c in cases]}, sort_keys=True))
        return 0
    results = [_run_case(case, args.timeout, args.mode) for case in cases]
    overall = (
        "PASS"
        if all(r["status"] == "PASS" for r in results)
        else (
            "BLOCKED_ENV"
            if all(r["status"] in {"PASS", "BLOCKED_ENV"} for r in results)
            else "FAIL"
        )
    )
    record = {
        "workflow": "statewake-public-trial-regressions",
        "mode": args.mode,
        "manifest": str(args.manifest),
        "status": overall,
        "results": results,
        "publication_authorized": False,
    }
    if args.output:
        path = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(json.dumps(record, sort_keys=True))
    return (
        0
        if record["status"] == "PASS"
        else (2 if record["status"] == "BLOCKED_ENV" else 1)
    )


if __name__ == "__main__":
    raise SystemExit(main())
