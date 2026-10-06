"""Verify post-publication registry metadata and public bytes, then emit a receipt."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
for candidate in (PROJECT_ROOT, SOURCE_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from statewake.release_trust import (  # noqa: E402
    fetch_registry_publication,
    load_publication_execution_permit,
    load_release_publication_basis,
    write_registry_publication_receipt,
)


def main() -> int:
    """Reconcile one external registry publication against exact StateWake evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--basis", type=Path, required=True)
    parser.add_argument("--permit", type=Path, required=True)
    parser.add_argument("--target", choices=("testpypi", "pypi"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--retry-seconds", type=float, default=10.0)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if args.attempts <= 0:
        raise ValueError("registry reconciliation attempts must be positive")
    if args.retry_seconds < 0:
        raise ValueError("registry reconciliation retry delay must be non-negative")

    basis = load_release_publication_basis(args.basis)
    permit = load_publication_execution_permit(args.permit)
    if (
        basis.target_repository != args.target
        or permit.target_repository != args.target
    ):
        raise PermissionError(
            "registry reconciliation target does not match publication evidence"
        )

    last_error: ConnectionError | None = None
    for attempt in range(1, args.attempts + 1):
        try:
            receipt = fetch_registry_publication(basis, permit, timeout=args.timeout)
            output = (
                args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
            )
            write_registry_publication_receipt(receipt, output)
            payload = receipt.to_dict()
            payload["receipt_digest"] = receipt.digest
            payload["attempt"] = attempt
            print(json.dumps(payload, sort_keys=True))
            return 0
        except ConnectionError as exc:
            last_error = exc
            if attempt == args.attempts:
                break
            time.sleep(args.retry_seconds)
    assert last_error is not None
    raise last_error


if __name__ == "__main__":
    raise SystemExit(main())
