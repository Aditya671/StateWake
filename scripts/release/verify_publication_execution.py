"""Fail closed unless exact distributions still have active publication authority."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
for candidate in (PROJECT_ROOT, SOURCE_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from statewake.adapters.human_approval import WorkspaceHumanApprovalStore  # noqa: E402
from statewake.release_trust import (  # noqa: E402
    issue_publication_execution_permit,
    load_release_publication_basis,
    write_publication_execution_permit,
)


def main() -> int:
    """Revalidate artifacts and active approval immediately before publishing."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--basis", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--verification-evidence", type=Path, required=True)
    parser.add_argument("--target", choices=("testpypi", "pypi"), required=True)
    parser.add_argument("--expected-producer-id")
    parser.add_argument("--expected-source-revision")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    basis = load_release_publication_basis(args.basis)
    if basis.target_repository != args.target:
        raise PermissionError("execution target does not match publication basis")
    expected_revision = (
        args.expected_source_revision or os.environ.get("GITHUB_SHA", "").strip()
    )
    if expected_revision and basis.source_revision != expected_revision:
        raise PermissionError(
            "execution source revision does not match publication basis"
        )
    expected_producer = args.expected_producer_id
    if not expected_producer:
        repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
        if not repository:
            raise ValueError("expected producer id or GITHUB_REPOSITORY is required")
        expected_producer = f"github-actions:{repository}"

    permit = issue_publication_execution_permit(
        WorkspaceHumanApprovalStore(args.workspace),
        basis,
        artifact_root=args.dist,
        expected_producer_id=expected_producer,
        verification_evidence_path=args.verification_evidence,
    )
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    write_publication_execution_permit(permit, output)
    payload = permit.to_dict()
    payload["permit_digest"] = permit.digest
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
