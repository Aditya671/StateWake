"""Create the exact distribution/verification basis for one package publication target."""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from hashlib import sha256
from pathlib import Path
from typing import cast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = PROJECT_ROOT / "src"
for candidate in (PROJECT_ROOT, SOURCE_ROOT):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from statewake.release_trust import (  # noqa: E402
    ArtifactDigest,
    PublicationTarget,
    ReleasePublicationBasis,
    write_release_publication_basis,
)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _project_identity() -> tuple[str, str]:
    payload = tomllib.loads(
        (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    return str(payload["project"]["name"]), str(payload["project"]["version"])


def _candidate_evidence(path: Path, *, version: str) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
        raise ValueError("release-candidate evidence root must be an object")
    payload = cast(dict[str, object], raw)
    if payload.get("status") != "passed":
        raise ValueError("release-candidate evidence is not passed")
    if payload.get("version") != version:
        raise ValueError(
            "release-candidate evidence version does not match the package"
        )
    if payload.get("publication_authorized") is not False:
        raise ValueError(
            "release-candidate verification must remain separate from publication authorization"
        )
    source_digest = payload.get("source_tree_sha256")
    if not isinstance(source_digest, str) or len(source_digest) != 64:
        raise ValueError("release-candidate evidence is missing source_tree_sha256")
    return payload


def _artifacts(dist: Path) -> tuple[ArtifactDigest, ...]:
    root = dist.expanduser().resolve(strict=True)
    items: list[ArtifactDigest] = []
    for path in sorted(root.iterdir(), key=lambda value: value.name):
        if path.is_symlink() or not path.is_file():
            raise ValueError("distribution directory must contain regular files only")
        if path.suffix == ".whl":
            media_type = "application/zip"
        elif path.name.endswith(".tar.gz"):
            media_type = "application/gzip"
        else:
            raise ValueError(f"unsupported publication artifact: {path.name}")
        items.append(
            ArtifactDigest(
                path.name,
                _sha256(path),
                path.stat().st_size,
                media_type,
            )
        )
    if not items:
        raise ValueError("distribution directory contains no publication artifacts")
    return tuple(items)


def main() -> int:
    """Create one exact publication basis from verified release inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("testpypi", "pypi"), required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--verification-evidence", type=Path, required=True)
    parser.add_argument(
        "--source-revision",
        "--expected-source-revision",
        dest="source_revision",
        required=True,
        help=(
            "exact source revision for the publication basis; "
            "--expected-source-revision is retained as a backwards-compatible alias"
        ),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    distribution, version = _project_identity()
    verification_path = args.verification_evidence.expanduser().resolve(strict=True)
    evidence = _candidate_evidence(verification_path, version=version)
    source_digest = cast(str, evidence["source_tree_sha256"])
    basis = ReleasePublicationBasis(
        distribution=distribution,
        version=version,
        target_repository=cast(PublicationTarget, args.target),
        source_revision=args.source_revision,
        source_tree_sha256=source_digest,
        verification_evidence_kind="release-candidate-evidence",
        verification_evidence_sha256=_sha256(verification_path),
        artifacts=_artifacts(args.dist),
        caveats=(),
    )
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    write_release_publication_basis(basis, output)
    print(
        json.dumps(
            {"status": "created", "basis_digest": basis.digest, **basis.to_dict()},
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
