"""Append one verified current registry lifecycle observation to canonical history."""

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
    RegistryPublicationLifecycleStore,
    fetch_registry_publication_lifecycle,
    load_publication_execution_permit,
    load_registry_publication_receipt,
    load_release_publication_basis,
)


def main() -> int:
    """Observe current registry state and append it to the receipt-bound lifecycle."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--basis", type=Path, required=True)
    parser.add_argument("--permit", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--target", choices=("testpypi", "pypi"), required=True)
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--retry-seconds", type=float, default=10.0)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if args.attempts <= 0:
        raise ValueError("registry lifecycle attempts must be positive")
    if args.retry_seconds < 0:
        raise ValueError("registry lifecycle retry delay must be non-negative")

    basis = load_release_publication_basis(args.basis)
    permit = load_publication_execution_permit(args.permit)
    receipt = load_registry_publication_receipt(args.receipt)
    if (
        basis.target_repository != args.target
        or permit.target_repository != args.target
        or receipt.target_repository != args.target
    ):
        raise PermissionError(
            "registry lifecycle target does not match publication evidence"
        )

    history_path = (
        args.history if args.history.is_absolute() else PROJECT_ROOT / args.history
    )
    store = RegistryPublicationLifecycleStore(history_path)
    history = store.read(receipt, basis, permit)
    previous = history[-1] if history else None

    last_error: ConnectionError | None = None
    for attempt in range(1, args.attempts + 1):
        try:
            observation = fetch_registry_publication_lifecycle(
                receipt,
                basis,
                permit,
                previous=previous,
                timeout=args.timeout,
            )
            created = store.append(observation, receipt, basis, permit)
            payload = observation.to_dict()
            payload["observation_digest"] = observation.digest
            payload["created"] = created
            payload["attempt"] = attempt
            payload["history_count"] = len(history) + (1 if created else 0)
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
