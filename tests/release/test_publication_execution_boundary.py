"""Exercise release scripts that connect canonical approval to external publishing."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from typing import cast

from statewake.release_trust import (
    ArtifactDigest,
    PublicationTarget,
    ReleasePublicationBasis,
    write_release_publication_basis,
)

ROOT = Path(__file__).resolve().parents[2]


def _basis(tmp_path: Path, *, target: str = "pypi") -> tuple[Path, Path, Path]:
    dist = tmp_path / "dist"
    dist.mkdir()
    artifact = dist / "statewake_ai-0.4.1-py3-none-any.whl"
    artifact.write_bytes(b"wheel")
    verification = tmp_path / "candidate.json"
    verification.write_bytes(b"verified candidate")
    basis = ReleasePublicationBasis(
        distribution="statewake-ai",
        version="0.4.1",
        target_repository=cast(PublicationTarget, target),
        source_revision="deadbeef",
        source_tree_sha256="a" * 64,
        verification_evidence_kind="release-candidate-evidence",
        verification_evidence_sha256=sha256(verification.read_bytes()).hexdigest(),
        artifacts=(
            ArtifactDigest(
                artifact.name,
                sha256(artifact.read_bytes()).hexdigest(),
                artifact.stat().st_size,
                "application/zip",
            ),
        ),
    )
    path = tmp_path / "basis.json"
    write_release_publication_basis(basis, path)
    return path, dist, verification


def _run(
    script: str, args: list[str], *, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((str(ROOT / "src"), str(ROOT))),
    }
    environment.update(env)
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/release" / script), *args],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_production_github_release_authorizes_exact_basis_then_issues_permit(
    tmp_path: Path,
) -> None:
    basis, dist, verification = _basis(tmp_path)
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {
                "action": "published",
                "release": {
                    "draft": False,
                    "prerelease": False,
                    "tag_name": "v0.4.1",
                    "author": {"login": "release-owner", "type": "User"},
                },
            }
        ),
        encoding="utf-8",
    )
    workspace = tmp_path / "approval"
    env = {
        "GITHUB_EVENT_NAME": "release",
        "GITHUB_EVENT_PATH": str(event),
        "GITHUB_ACTOR": "release-owner",
        "GITHUB_REPOSITORY": "example/statewake",
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": "deadbeef",
    }
    auth = _run(
        "record_publication_authorization_from_github.py",
        ["--basis", str(basis), "--workspace", str(workspace), "--target", "pypi"],
        env=env,
    )
    assert auth.returncode == 0, auth.stderr
    payload = json.loads(auth.stdout)
    assert payload["publication_authorized"] is True
    permit = tmp_path / "permit.json"
    verified = _run(
        "verify_publication_execution.py",
        [
            "--basis",
            str(basis),
            "--workspace",
            str(workspace),
            "--dist",
            str(dist),
            "--verification-evidence",
            str(verification),
            "--target",
            "pypi",
            "--output",
            str(permit),
        ],
        env=env,
    )
    assert verified.returncode == 0, verified.stderr
    result = json.loads(permit.read_text(encoding="utf-8"))
    assert result["publication_authorized"] is True
    assert result["release_published"] is False


def test_release_tag_or_artifact_drift_blocks_publication(tmp_path: Path) -> None:
    basis, dist, verification = _basis(tmp_path)
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps(
            {
                "action": "published",
                "release": {
                    "draft": False,
                    "prerelease": False,
                    "tag_name": "v0.4.0",
                    "author": {"login": "release-owner", "type": "User"},
                },
            }
        ),
        encoding="utf-8",
    )
    workspace = tmp_path / "approval"
    env = {
        "GITHUB_EVENT_NAME": "release",
        "GITHUB_EVENT_PATH": str(event),
        "GITHUB_ACTOR": "release-owner",
        "GITHUB_REPOSITORY": "example/statewake",
        "GITHUB_RUN_ID": "123",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": "deadbeef",
    }
    denied = _run(
        "record_publication_authorization_from_github.py",
        ["--basis", str(basis), "--workspace", str(workspace), "--target", "pypi"],
        env=env,
    )
    assert denied.returncode != 0

    event.write_text(
        json.dumps(
            {
                "action": "published",
                "release": {
                    "draft": False,
                    "prerelease": False,
                    "tag_name": "v0.4.1",
                    "author": {"login": "release-owner", "type": "User"},
                },
            }
        ),
        encoding="utf-8",
    )
    allowed = _run(
        "record_publication_authorization_from_github.py",
        ["--basis", str(basis), "--workspace", str(workspace), "--target", "pypi"],
        env=env,
    )
    assert allowed.returncode == 0, allowed.stderr
    (dist / "statewake_ai-0.4.1-py3-none-any.whl").write_bytes(b"changed")
    execution = _run(
        "verify_publication_execution.py",
        [
            "--basis",
            str(basis),
            "--workspace",
            str(workspace),
            "--dist",
            str(dist),
            "--verification-evidence",
            str(verification),
            "--target",
            "pypi",
            "--output",
            str(tmp_path / "permit.json"),
        ],
        env=env,
    )
    assert execution.returncode != 0


def test_testpypi_requires_explicit_dispatch_input(tmp_path: Path) -> None:
    basis, _dist, _verification = _basis(tmp_path, target="testpypi")
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"inputs": {"repository": "testpypi"}}), encoding="utf-8"
    )
    env = {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_EVENT_PATH": str(event),
        "GITHUB_ACTOR": "developer",
        "GITHUB_REPOSITORY": "example/statewake",
        "GITHUB_RUN_ID": "222",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": "deadbeef",
    }
    result = _run(
        "record_publication_authorization_from_github.py",
        [
            "--basis",
            str(basis),
            "--workspace",
            str(tmp_path / "approval"),
            "--target",
            "testpypi",
        ],
        env=env,
    )
    assert result.returncode == 0, result.stderr
