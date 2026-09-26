"""Verify Tier 5 continuous security assurance against a promoted snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from scripts.common.release_scope import release_input_files  # noqa: E402

INVARIANT_BY_PREFIX: Final[tuple[tuple[str, str], ...]] = (
    ("src/statewake/adapters/key_management.py", "cryptographic-boundary"),
    ("src/statewake/domain/trust_anchor.py", "trust-anchor"),
    ("src/statewake/adapters/deployment_security.py", "authorization-boundary"),
    ("src/statewake/adapters/security_audit.py", "security-audit"),
)
FAMILY_TO_INVARIANTS: Final[dict[str, tuple[str, ...]]] = {
    "evidence-provenance-state": (
        "evidence-integrity",
        "provenance-integrity",
        "reliability-state-integrity",
        "attestation-integrity",
    ),
    "crypto-trust": ("cryptographic-boundary", "trust-anchor"),
    "deployment-boundary": ("authorization-boundary", "security-audit"),
    "archive-proof": ("portable-proof-integrity",),
    "persistence-recovery": (
        "persistence-integrity",
        "recovery-security-assumptions",
    ),
    "dependencies-configuration": ("all-tier4-security-invariants",),
    "security-evidence": ("tier4-security-assurance-evidence",),
    "generic-source": ("conservative-security-re-assurance",),
}

SECURITY_EVIDENCE_PATHS: Final[tuple[str, ...]] = (
    "docs/security/THREAT_MODEL.md",
    "docs/security/CONTROL_TEST_MATRIX.md",
    "docs/security/INCIDENT_RECOVERY.md",
    "docs/security/security_assurance_boundary.md",
    "docs/adr/0004-security-architecture.md",
)


@dataclass(frozen=True, slots=True)
class Change:
    """Describe one repository path whose content differs from the baseline."""

    path: str
    families: tuple[str, ...]
    invariants: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AssuranceResult:
    """Represent one Tier 5 assurance calculation."""

    generated_at: str
    state: str
    candidate_fingerprint: str
    baseline_fingerprint: str
    changed_files: tuple[str, ...]
    impacted_invariants: tuple[str, ...]
    reverified: bool
    reverify_returncode: int | None
    limitation: str


def _included_files(root: Path) -> Iterable[Path]:
    """Yield repository files while excluding runtime-generated directories."""
    yield from release_input_files(root)


def _digest_file(path: Path) -> str:
    """Return a SHA-256 digest for one repository file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot(root: Path, *, exclude: Iterable[str] = ()) -> dict[str, str]:
    """Return a relative-path-to-SHA-256 snapshot for a repository."""
    excluded = set(exclude)
    return {
        path.relative_to(root).as_posix(): _digest_file(path)
        for path in _included_files(root)
        if path.relative_to(root).as_posix() not in excluded
    }


def snapshot_fingerprint(snapshot_data: dict[str, str]) -> str:
    """Return a stable SHA-256 fingerprint for a repository snapshot."""
    payload = "\n".join(
        f"{path} {digest}" for path, digest in sorted(snapshot_data.items())
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_snapshot_manifest(path: Path, snapshot_data: dict[str, str]) -> None:
    """Write a deterministic path/digest baseline manifest."""
    path.write_text(
        "".join(
            f"{digest}  {name}\n" for name, digest in sorted(snapshot_data.items())
        ),
        encoding="utf-8",
        newline="\n",
    )


def read_snapshot_manifest(path: Path) -> dict[str, str]:
    """Read a path/digest baseline manifest."""
    records: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        digest, name = raw_line.split("  ", 1)
        if len(digest) != 64:
            raise ValueError(f"invalid SHA-256 digest in baseline: {name}")
        records[name] = digest
    return records


def classify_change(path: str) -> Change:
    """Classify one changed path conservatively for security re-assurance."""
    families: set[str] = set()
    normalized = path.replace("\\", "/")
    if normalized in SECURITY_EVIDENCE_PATHS:
        families.add("security-evidence")
    if normalized.startswith(
        (
            "src/statewake/domain/evidence",
            "src/statewake/domain/provenance",
        )
    ):
        families.add("evidence-provenance-state")
    if normalized.startswith("src/statewake/domain/reliability"):
        families.add("evidence-provenance-state")
    if normalized.startswith(
        (
            "src/statewake/adapters/key_management.py",
            "src/statewake/domain/trust_anchor.py",
        )
    ):
        families.add("crypto-trust")
    if normalized.startswith(
        (
            "src/statewake/adapters/deployment_security.py",
            "src/statewake/adapters/security_audit.py",
        )
    ):
        families.add("deployment-boundary")
    if any(
        token in normalized for token in ("archive", "proof_bundle", "release_proof")
    ):
        families.add("archive-proof")
    if any(
        token in normalized
        for token in ("persistence", "recovery", "storage", "operations")
    ):
        families.add("persistence-recovery")
    if normalized in {"pyproject.toml", "uv.lock"} or normalized.startswith("config/"):
        families.add("dependencies-configuration")
    if normalized.startswith("src/") and not families:
        families.add("generic-source")
    if not families:
        return Change(normalized, (), ())
    invariants: set[str] = set()
    for family in families:
        invariants.update(FAMILY_TO_INVARIANTS[family])
    for source_path, invariant in INVARIANT_BY_PREFIX:
        if normalized == source_path:
            invariants.add(invariant)
    return Change(normalized, tuple(sorted(families)), tuple(sorted(invariants)))


def changed_paths(baseline: dict[str, str], current: dict[str, str]) -> tuple[str, ...]:
    """Return paths added, removed, or content-changed from the baseline."""
    names = set(baseline) | set(current)
    return tuple(
        sorted(name for name in names if baseline.get(name) != current.get(name))
    )


def _security_assurance_verifier_command(root: Path) -> list[str]:
    """Return the existing Tier 4 verifier command for the current Python runtime."""
    return [
        sys.executable,
        str(root / "scripts/security/verify_security_assurance_boundary.py"),
    ]


def run_security_assurance_reverification(root: Path) -> tuple[bool, int]:
    """Run the canonical Tier 4 evidence verifier without mutating product code."""
    completed = subprocess.run(
        _security_assurance_verifier_command(root),
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return completed.returncode == 0, completed.returncode


def assess(
    root: Path,
    baseline_path: Path,
    *,
    reverify: bool = True,
) -> AssuranceResult:
    """Assess whether the current candidate is still security-assured."""
    baseline = read_snapshot_manifest(baseline_path)
    current = snapshot(root, exclude={baseline_path.relative_to(root).as_posix()})
    changed = changed_paths(baseline, current)
    classifications = [classify_change(path) for path in changed]
    impacted = tuple(
        sorted(
            invariant for change in classifications for invariant in change.invariants
        )
    )
    baseline_fingerprint = snapshot_fingerprint(baseline)
    candidate_fingerprint = snapshot_fingerprint(current)
    reverified = False
    returncode: int | None = None
    state = "VERIFIED"
    if impacted:
        state = "STALE"
        if reverify:
            state = "REVERIFYING"
            reverified, returncode = run_security_assurance_reverification(root)
            state = "VERIFIED" if reverified else "ASSURANCE_BROKEN"
    limitation = (
        "Independent clean-copy execution remains a separate agent verification, "
        "not an external human security audit or penetration test."
    )
    return AssuranceResult(
        generated_at=datetime.now(UTC).isoformat(),
        state=state,
        candidate_fingerprint=candidate_fingerprint,
        baseline_fingerprint=baseline_fingerprint,
        changed_files=changed,
        impacted_invariants=impacted,
        reverified=reverified,
        reverify_returncode=returncode,
        limitation=limitation,
    )


def main() -> int:
    """Run Tier 5 assurance and optionally write a JSON evidence record."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("docs/security/security_assurance_baseline_manifest.txt"),
    )
    parser.add_argument("--no-reverify", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    baseline = args.baseline if args.baseline.is_absolute() else root / args.baseline
    result = assess(root, baseline, reverify=not args.no_reverify)
    payload = json.dumps(asdict(result), indent=2, sort_keys=True) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else root / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0 if result.state == "VERIFIED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
