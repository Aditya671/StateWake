"""Record canonical publication approval from a trusted GitHub Actions event boundary."""

from __future__ import annotations

import argparse
import json
import os
import sys
from hashlib import sha256
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
for candidate in (PROJECT_ROOT, SOURCE_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from statewake.adapters.human_approval import WorkspaceHumanApprovalStore  # noqa: E402
from statewake.release_trust import (  # noqa: E402
    load_release_publication_basis,
    record_publication_authorization,
)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required at the publication boundary")
    return value


def _event(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
        raise ValueError("GitHub event payload root must be an object")
    return raw


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be an object")
    return value


def _github_actor(
    event: dict[str, object], *, event_name: str, fallback_actor: str
) -> tuple[str, str, str]:
    if event_name == "release":
        if event.get("action") != "published":
            raise PermissionError("production publication requires release.published")
        release = _mapping(event.get("release"), "release")
        if release.get("draft") is not False or release.get("prerelease") is not False:
            raise PermissionError(
                "production publication requires a non-draft, non-prerelease GitHub Release"
            )
        author = _mapping(release.get("author"), "release.author")
        login = author.get("login")
        actor_type = author.get("type")
        if not isinstance(login, str) or not login.strip():
            raise ValueError("release.author.login is required")
        if actor_type not in {None, "User"}:
            raise PermissionError("production release author must be a GitHub user")
        tag = release.get("tag_name")
        if not isinstance(tag, str) or not tag.strip():
            raise ValueError("release.tag_name is required")
        return login, "github-release-publisher", tag
    if event_name == "workflow_dispatch":
        inputs = _mapping(event.get("inputs", {}), "inputs")
        if inputs.get("repository") != "testpypi":
            raise PermissionError("manual publication is limited to TestPyPI")
        return fallback_actor, "github-workflow-dispatcher", ""
    raise PermissionError("unsupported GitHub event for publication authorization")


def main() -> int:
    """Record canonical authorization for the exact GitHub publication event."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--basis", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--target", choices=("testpypi", "pypi"), required=True)
    args = parser.parse_args()

    basis = load_release_publication_basis(args.basis)
    if basis.target_repository != args.target:
        raise PermissionError("publication target does not match the canonical basis")
    event_name = _required_env("GITHUB_EVENT_NAME")
    actor = _required_env("GITHUB_ACTOR")
    repository = _required_env("GITHUB_REPOSITORY")
    run_id = _required_env("GITHUB_RUN_ID")
    run_attempt = _required_env("GITHUB_RUN_ATTEMPT")
    source_revision = _required_env("GITHUB_SHA")
    if source_revision != basis.source_revision:
        raise PermissionError(
            "GitHub source revision does not match the canonical basis"
        )
    event = _event(Path(_required_env("GITHUB_EVENT_PATH")))
    actor_identity, actor_role, release_tag = _github_actor(
        event, event_name=event_name, fallback_actor=actor
    )
    if args.target == "pypi":
        if event_name != "release" or release_tag != f"v{basis.version}":
            raise PermissionError(
                "production publication requires the exact versioned GitHub Release"
            )
    elif event_name != "workflow_dispatch":
        raise PermissionError(
            "TestPyPI publication requires explicit workflow_dispatch"
        )

    producer_id = f"github-actions:{repository}"
    canonical_run_id = f"github-run:{run_id}:{run_attempt}"
    event_identity = sha256(
        json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    approval, created = record_publication_authorization(
        WorkspaceHumanApprovalStore(args.workspace),
        basis,
        actor_identity_ref=f"github-user:{actor_identity}",
        actor_role=actor_role,
        producer_id=producer_id,
        run_id=canonical_run_id,
        reason=(
            f"Authorize {basis.distribution} {basis.version} for {args.target} from "
            f"GitHub {event_name} event {event_identity}."
        ),
        idempotency_key=f"publication:{args.target}:{run_id}:{run_attempt}",
    )
    print(
        json.dumps(
            {
                "status": "authorized",
                "created": created,
                "basis_digest": basis.digest,
                "target_repository": args.target,
                "producer_id": producer_id,
                "authorization_receipt_id": approval.receipt.receipt_id,
                "authorization_receipt_digest": approval.receipt.digest,
                "publication_authorized": True,
                "release_published": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
