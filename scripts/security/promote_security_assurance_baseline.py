"""Promote the verified StateWake continuous-security baseline explicitly."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_CONFIG_BOOTSTRAP = Path(__file__).resolve().parents[2]
if str(PROJECT_CONFIG_BOOTSTRAP) not in sys.path:
    sys.path.insert(0, str(PROJECT_CONFIG_BOOTSTRAP))

from scripts.security.verify_continuous_security_assurance import (  # noqa: E402
    AssuranceResult,
    assess,
    run_security_assurance_reverification,
    snapshot,
    write_snapshot_manifest,
)


@dataclass(frozen=True, slots=True)
class PromotionResult:
    """Record explicit security-baseline promotion evidence."""

    assurance: AssuranceResult
    baseline_updated: bool
    reverification_performed: bool
    reverification_returncode: int | None


def promote_security_assurance_baseline(
    root: Path,
    baseline: Path,
) -> PromotionResult:
    """Reverify a changed candidate, promote it, and prove zero drift."""
    root = root.resolve()
    baseline = baseline.resolve()
    result = assess(root, baseline, reverify=True)
    baseline_updated = bool(result.changed_files)
    reverification_performed = result.reverified
    reverification_returncode = result.reverify_returncode
    if result.changed_files:
        if not result.reverified:
            verified, returncode = run_security_assurance_reverification(root)
            reverification_performed = True
            reverification_returncode = returncode
            if not verified:
                raise RuntimeError(
                    "security assurance re-verification failed before baseline promotion "
                    f"with exit code {returncode}"
                )
        if result.state != "VERIFIED":
            raise RuntimeError(
                "cannot promote a security snapshot that is not VERIFIED"
            )
        current = snapshot(root, exclude_paths={baseline})
        write_snapshot_manifest(baseline, current)
        result = assess(root, baseline, reverify=False)
        if result.changed_files or result.state != "VERIFIED":
            raise RuntimeError(
                "promoted security snapshot did not converge to zero drift"
            )
    return PromotionResult(
        assurance=result,
        baseline_updated=baseline_updated,
        reverification_performed=reverification_performed,
        reverification_returncode=reverification_returncode,
    )


def main() -> int:
    """Promote the current verified candidate into the security baseline."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("docs/security/security_assurance_baseline_manifest.txt"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    baseline = args.baseline if args.baseline.is_absolute() else root / args.baseline
    try:
        promotion = promote_security_assurance_baseline(root, baseline)
    except (RuntimeError, ValueError) as exc:
        print(json.dumps({"status": "failed", "failure": str(exc)}, sort_keys=True))
        return 1
    result = promotion.assurance
    payload_data = {
        **asdict(result),
        "baseline_current": not result.changed_files,
        "baseline_updated": promotion.baseline_updated,
        "promotion_reverification_performed": promotion.reverification_performed,
        "promotion_reverification_returncode": promotion.reverification_returncode,
        "status": "promoted",
    }
    payload = json.dumps(payload_data, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else root / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
