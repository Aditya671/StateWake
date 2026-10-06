"""Canonical release-publication authorization and execution boundary.

Publication authorization is deliberately separate from release verification. This
module reuses StateWake's canonical ``HumanApprovalContract`` persistence/lifecycle
rather than inventing a second approval authority. A publication execution permit
is issued only after the exact publication basis, distribution bytes, verification
evidence, and currently active approval lifecycle are re-checked.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Literal, cast

from statewake.adapters.human_approval import (
    HumanApprovalEvidenceRecord,
    HumanApprovalLifecycleItem,
    HumanApprovalRevocationEvidenceRecord,
    WorkspaceHumanApprovalStore,
)
from statewake.release_trust.model import ArtifactDigest, ReleaseTrustBundle
from statewake.utils.json_support import JsonValue, require_object, require_string
from statewake.utils.time import parse_datetime

PublicationTarget = Literal["testpypi", "pypi"]
PUBLICATION_ACTION = "publish-release"
PUBLICATION_PROFILE_ID = "release-publication-authorization.v1"
PUBLICATION_PROFILE_VERSION = "1"
_BASIS_SCHEMA = "release-publication-basis.v1"
_PERMIT_SCHEMA = "release-publication-permit.v1"
_ALLOWED_TARGETS: frozenset[str] = frozenset({"testpypi", "pypi"})


def _canonical(payload: dict[str, object]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _require_digest(value: str, field: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")


def _require_text(value: str, field: str) -> None:
    if not value.strip():
        raise ValueError(f"{field} must not be empty")


def _artifact_from_dict(payload: dict[str, JsonValue]) -> ArtifactDigest:
    size_raw = payload.get("size_bytes")
    if isinstance(size_raw, bool) or not isinstance(size_raw, int):
        raise ValueError("publication artifact size_bytes must be an integer")
    return ArtifactDigest(
        name=require_string(payload.get("name"), field="artifact.name"),
        sha256=require_string(payload.get("sha256"), field="artifact.sha256"),
        size_bytes=size_raw,
        media_type=require_string(
            payload.get("media_type"), field="artifact.media_type"
        ),
    )


@dataclass(frozen=True, slots=True)
class ReleasePublicationBasis:
    """Exact immutable basis on which one registry publication may be authorized."""

    distribution: str
    version: str
    target_repository: PublicationTarget
    source_revision: str
    source_tree_sha256: str
    verification_evidence_kind: str
    verification_evidence_sha256: str
    artifacts: tuple[ArtifactDigest, ...]
    release_bundle_digest: str | None = None
    caveats: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate publication identity, target, artifacts, and caveats."""
        for field in (
            "distribution",
            "version",
            "source_revision",
            "verification_evidence_kind",
        ):
            _require_text(str(getattr(self, field)), f"publication_basis.{field}")
        if self.target_repository not in _ALLOWED_TARGETS:
            raise ValueError("publication_basis.target_repository is unsupported")
        _require_digest(self.source_tree_sha256, "publication_basis.source_tree_sha256")
        _require_digest(
            self.verification_evidence_sha256,
            "publication_basis.verification_evidence_sha256",
        )
        if self.release_bundle_digest is not None:
            _require_digest(
                self.release_bundle_digest,
                "publication_basis.release_bundle_digest",
            )
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "caveats", tuple(self.caveats))
        if not self.artifacts:
            raise ValueError(
                "publication basis requires at least one distribution artifact"
            )
        names: set[str] = set()
        for artifact in self.artifacts:
            candidate = PurePosixPath(artifact.name)
            if (
                candidate.is_absolute()
                or candidate.name != artifact.name
                or artifact.name in {"", ".", ".."}
                or "\\" in artifact.name
            ):
                raise ValueError("publication artifact name must be one safe basename")
            if artifact.name in names:
                raise ValueError("publication artifact names must be unique")
            names.add(artifact.name)
        if any(not item.strip() for item in self.caveats):
            raise ValueError("publication basis caveats must not contain blank values")

    @property
    def digest(self) -> str:
        """Return the canonical publication-basis identity."""
        return sha256(_canonical(self.to_dict())).hexdigest()

    @property
    def scope(self) -> str:
        """Return the exact approval scope represented by this basis."""
        return publication_scope(self.target_repository)

    @property
    def candidate_identity(self) -> str:
        """Return a stable human-readable candidate identity."""
        return f"{self.distribution}=={self.version}@{self.target_repository}"

    def to_dict(self) -> dict[str, object]:
        """Serialize the publication basis deterministically."""
        return {
            "schema_version": _BASIS_SCHEMA,
            "distribution": self.distribution,
            "version": self.version,
            "target_repository": self.target_repository,
            "source_revision": self.source_revision,
            "source_tree_sha256": self.source_tree_sha256,
            "verification_evidence": {
                "kind": self.verification_evidence_kind,
                "sha256": self.verification_evidence_sha256,
            },
            "artifacts": [item.to_dict() for item in self.artifacts],
            "release_bundle_digest": self.release_bundle_digest,
            "caveats": list(self.caveats),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> ReleasePublicationBasis:
        """Parse and validate one persisted publication basis."""
        if (
            require_string(payload.get("schema_version"), field="schema_version")
            != _BASIS_SCHEMA
        ):
            raise ValueError("unsupported release publication basis schema")
        verification = require_object(
            payload.get("verification_evidence"), field="verification_evidence"
        )
        artifacts_raw = payload.get("artifacts")
        if not isinstance(artifacts_raw, list):
            raise ValueError("artifacts must be a JSON array")
        artifacts = tuple(
            _artifact_from_dict(dict(require_object(item, field=f"artifacts[{index}]")))
            for index, item in enumerate(artifacts_raw)
        )
        target = require_string(
            payload.get("target_repository"), field="target_repository"
        )
        if target not in _ALLOWED_TARGETS:
            raise ValueError("unsupported publication target repository")
        release_bundle_digest_raw = payload.get("release_bundle_digest")
        if release_bundle_digest_raw is None:
            release_bundle_digest = None
        else:
            release_bundle_digest = require_string(
                release_bundle_digest_raw, field="release_bundle_digest"
            )
        caveats_raw = payload.get("caveats", [])
        if not isinstance(caveats_raw, list):
            raise ValueError("caveats must be a JSON array")
        caveats = tuple(
            require_string(item, field=f"caveats[{index}]")
            for index, item in enumerate(caveats_raw)
        )
        return cls(
            distribution=require_string(
                payload.get("distribution"), field="distribution"
            ),
            version=require_string(payload.get("version"), field="version"),
            target_repository=cast(PublicationTarget, target),
            source_revision=require_string(
                payload.get("source_revision"), field="source_revision"
            ),
            source_tree_sha256=require_string(
                payload.get("source_tree_sha256"), field="source_tree_sha256"
            ),
            verification_evidence_kind=require_string(
                verification.get("kind"), field="verification_evidence.kind"
            ),
            verification_evidence_sha256=require_string(
                verification.get("sha256"), field="verification_evidence.sha256"
            ),
            artifacts=artifacts,
            release_bundle_digest=release_bundle_digest,
            caveats=caveats,
        )


@dataclass(frozen=True, slots=True)
class PublicationAuthorizationState:
    """Current canonical lifecycle state for one exact publication basis."""

    basis_digest: str
    target_repository: PublicationTarget
    expected_producer_id: str
    lifecycle: tuple[HumanApprovalLifecycleItem, ...]

    @property
    def active(self) -> tuple[HumanApprovalEvidenceRecord, ...]:
        """Return only active approvals from the configured publication authority."""
        return tuple(
            item.approval
            for item in self.lifecycle
            if item.status == "active"
            and item.approval.contract.producer_id == self.expected_producer_id
            and item.approval.contract.approval_action == PUBLICATION_ACTION
            and item.approval.contract.scope
            == publication_scope(self.target_repository)
        )

    @property
    def publication_authorized(self) -> bool:
        """Whether at least one exact-authority approval is currently active."""
        return bool(self.active)

    def to_dict(self) -> dict[str, object]:
        """Return an operator-facing lifecycle projection."""
        return {
            "basis_digest": self.basis_digest,
            "target_repository": self.target_repository,
            "expected_producer_id": self.expected_producer_id,
            "publication_authorized": self.publication_authorized,
            "active_approval_receipt_ids": [
                item.receipt.receipt_id for item in self.active
            ],
            "items": [item.to_dict() for item in self.lifecycle],
        }


@dataclass(frozen=True, slots=True)
class PublicationExecutionPermit:
    """Fresh point-in-time handoff that permits an external publication executor."""

    basis_digest: str
    target_repository: PublicationTarget
    source_revision: str
    artifact_sha256: tuple[tuple[str, str], ...]
    authorization_receipt_ids: tuple[str, ...]
    authorization_receipt_digests: tuple[str, ...]
    issued_at: datetime

    def __post_init__(self) -> None:
        """Validate the fresh execution permit and its authorization references."""
        _require_digest(self.basis_digest, "publication_permit.basis_digest")
        if self.target_repository not in _ALLOWED_TARGETS:
            raise ValueError("publication_permit.target_repository is unsupported")
        _require_text(self.source_revision, "publication_permit.source_revision")
        if self.issued_at.tzinfo is None:
            raise ValueError("publication_permit.issued_at must be timezone-aware")
        if not self.authorization_receipt_ids:
            raise ValueError(
                "publication permit requires active authorization evidence"
            )
        if len(self.authorization_receipt_ids) != len(
            self.authorization_receipt_digests
        ):
            raise ValueError(
                "publication permit authorization receipt vectors do not align"
            )
        for value in (
            *self.authorization_receipt_ids,
            *self.authorization_receipt_digests,
        ):
            _require_digest(value, "publication_permit.authorization_receipt")
        for name, digest in self.artifact_sha256:
            _require_text(name, "publication_permit.artifact_name")
            _require_digest(digest, "publication_permit.artifact_sha256")

    @property
    def digest(self) -> str:
        """Return the canonical execution-permit identity."""
        return sha256(_canonical(self.to_dict())).hexdigest()

    @classmethod
    def from_dict(cls, payload: dict[str, JsonValue]) -> PublicationExecutionPermit:
        """Parse and validate one persisted publication execution permit."""
        if (
            require_string(payload.get("schema_version"), field="schema_version")
            != _PERMIT_SCHEMA
        ):
            raise ValueError("unsupported release publication permit schema")
        target = require_string(
            payload.get("target_repository"), field="target_repository"
        )
        if target not in _ALLOWED_TARGETS:
            raise ValueError("unsupported publication target repository")
        if payload.get("publication_authorized") is not True:
            raise ValueError(
                "publication permit must record publication_authorized=true"
            )
        if payload.get("release_published") is not False:
            raise ValueError("publication permit cannot claim registry publication")
        if payload.get("external_execution_required") is not True:
            raise ValueError("publication permit must require external execution")
        artifacts_raw = payload.get("artifacts")
        if not isinstance(artifacts_raw, list):
            raise ValueError("publication permit artifacts must be a JSON array")
        artifacts: list[tuple[str, str]] = []
        for index, raw in enumerate(artifacts_raw):
            item = require_object(raw, field=f"artifacts[{index}]")
            artifacts.append(
                (
                    require_string(item.get("name"), field=f"artifacts[{index}].name"),
                    require_string(
                        item.get("sha256"), field=f"artifacts[{index}].sha256"
                    ),
                )
            )
        ids_raw = payload.get("authorization_receipt_ids")
        digests_raw = payload.get("authorization_receipt_digests")
        if not isinstance(ids_raw, list) or not isinstance(digests_raw, list):
            raise ValueError(
                "publication permit authorization receipts must be JSON arrays"
            )
        return cls(
            basis_digest=require_string(
                payload.get("basis_digest"), field="basis_digest"
            ),
            target_repository=cast(PublicationTarget, target),
            source_revision=require_string(
                payload.get("source_revision"), field="source_revision"
            ),
            artifact_sha256=tuple(artifacts),
            authorization_receipt_ids=tuple(
                require_string(value, field=f"authorization_receipt_ids[{index}]")
                for index, value in enumerate(ids_raw)
            ),
            authorization_receipt_digests=tuple(
                require_string(value, field=f"authorization_receipt_digests[{index}]")
                for index, value in enumerate(digests_raw)
            ),
            issued_at=parse_datetime(
                require_string(payload.get("issued_at"), field="issued_at"),
                field="issued_at",
            ),
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the handoff without claiming publication occurred."""
        return {
            "schema_version": _PERMIT_SCHEMA,
            "basis_digest": self.basis_digest,
            "target_repository": self.target_repository,
            "source_revision": self.source_revision,
            "artifacts": [
                {"name": name, "sha256": digest}
                for name, digest in self.artifact_sha256
            ],
            "authorization_receipt_ids": list(self.authorization_receipt_ids),
            "authorization_receipt_digests": list(self.authorization_receipt_digests),
            "issued_at": self.issued_at.astimezone(UTC).isoformat(),
            "publication_authorized": True,
            "release_published": False,
            "external_execution_required": True,
            "limitations": [
                "This permit authorizes only the exact basis and target repository recorded here.",
                "The external publisher must re-run this gate immediately before publication; a later revocation or changed artifact invalidates a fresh permit.",
                "The permit records authorization to execute but is not evidence that the package registry accepted or published the release.",
            ],
        }


def publication_scope(target: PublicationTarget) -> str:
    """Return the bounded HumanApprovalContract scope for one package registry."""
    if target not in _ALLOWED_TARGETS:
        raise ValueError("unsupported publication target repository")
    return f"release-publication:{target}"


def publication_basis_from_release_trust(
    bundle: ReleaseTrustBundle,
    *,
    target_repository: PublicationTarget,
) -> ReleasePublicationBasis:
    """Bind publication authority to one exact release-trust bundle."""
    return ReleasePublicationBasis(
        distribution=bundle.source.distribution,
        version=bundle.source.version,
        target_repository=target_repository,
        source_revision=bundle.source.source_revision,
        source_tree_sha256=bundle.source.source_tree_sha256,
        verification_evidence_kind="release-trust-bundle",
        verification_evidence_sha256=bundle.digest,
        artifacts=bundle.artifacts,
        release_bundle_digest=bundle.digest,
        caveats=bundle.limitations,
    )


def write_release_publication_basis(basis: ReleasePublicationBasis, path: Path) -> None:
    """Persist one deterministic publication basis."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_canonical(basis.to_dict()) + b"\n")


def load_release_publication_basis(path: Path) -> ReleasePublicationBasis:
    """Load and verify one persisted publication basis."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
        raise ValueError("release publication basis root must be an object")
    return ReleasePublicationBasis.from_dict(cast(dict[str, JsonValue], raw))


def write_publication_execution_permit(
    permit: PublicationExecutionPermit, path: Path
) -> None:
    """Persist one canonical publication execution permit including its digest."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = permit.to_dict()
    payload["permit_digest"] = permit.digest
    path.write_bytes(_canonical(payload) + b"\n")


def load_publication_execution_permit(path: Path) -> PublicationExecutionPermit:
    """Load and verify one persisted publication execution permit."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or any(not isinstance(key, str) for key in raw):
        raise ValueError("release publication permit root must be an object")
    payload = cast(dict[str, JsonValue], raw)
    permit = PublicationExecutionPermit.from_dict(payload)
    recorded_digest = payload.get("permit_digest")
    if recorded_digest is not None:
        if require_string(recorded_digest, field="permit_digest") != permit.digest:
            raise ValueError(
                "release publication permit digest does not match contents"
            )
    return permit


def record_publication_authorization(
    store: WorkspaceHumanApprovalStore,
    basis: ReleasePublicationBasis,
    *,
    actor_identity_ref: str,
    actor_role: str,
    producer_id: str,
    run_id: str,
    reason: str,
    idempotency_key: str,
    supersedes_approval_receipt_id: str | None = None,
) -> tuple[HumanApprovalEvidenceRecord, bool]:
    """Append canonical publication approval using the existing approval authority."""
    return store.append(
        target_record_id=basis.digest,
        candidate_identity=basis.candidate_identity,
        candidate_digest=basis.digest,
        report_digest=basis.digest,
        profile_id=PUBLICATION_PROFILE_ID,
        profile_version=PUBLICATION_PROFILE_VERSION,
        actor_identity_ref=actor_identity_ref,
        actor_role=actor_role,
        producer_id=producer_id,
        run_id=run_id,
        approval_action=PUBLICATION_ACTION,
        scope=basis.scope,
        reason=reason,
        idempotency_key=idempotency_key,
        supersedes_approval_receipt_id=supersedes_approval_receipt_id,
    )


def revoke_publication_authorization(
    store: WorkspaceHumanApprovalStore,
    basis: ReleasePublicationBasis,
    *,
    target_approval_receipt_id: str,
    actor_identity_ref: str,
    actor_role: str,
    producer_id: str,
    run_id: str,
    reason: str,
    idempotency_key: str,
) -> tuple[HumanApprovalRevocationEvidenceRecord, bool]:
    """Revoke one active publication authorization without deleting history."""
    return store.revoke(
        target_record_id=basis.digest,
        target_approval_receipt_id=target_approval_receipt_id,
        candidate_identity=basis.candidate_identity,
        candidate_digest=basis.digest,
        report_digest=basis.digest,
        profile_id=PUBLICATION_PROFILE_ID,
        profile_version=PUBLICATION_PROFILE_VERSION,
        actor_identity_ref=actor_identity_ref,
        actor_role=actor_role,
        producer_id=producer_id,
        run_id=run_id,
        approval_action=PUBLICATION_ACTION,
        scope=basis.scope,
        reason=reason,
        idempotency_key=idempotency_key,
    )


def resolve_publication_authorization(
    store: WorkspaceHumanApprovalStore,
    basis: ReleasePublicationBasis,
    *,
    expected_producer_id: str,
) -> PublicationAuthorizationState:
    """Resolve fail-closed effective publication authority for one exact basis."""
    _require_text(expected_producer_id, "expected_producer_id")
    lifecycle = tuple(
        store.lifecycle_for_target(basis.digest, report_digest=basis.digest)
    )
    for item in lifecycle:
        contract = item.approval.contract
        metadata = contract.metadata or {}
        if (
            contract.approval_basis_digest != basis.digest
            or metadata.get("candidate_identity") != basis.candidate_identity
            or metadata.get("candidate_digest") != basis.digest
            or metadata.get("profile_id") != PUBLICATION_PROFILE_ID
            or metadata.get("profile_version") != PUBLICATION_PROFILE_VERSION
        ):
            raise ValueError(
                "publication approval lifecycle is not bound to the exact basis"
            )
    return PublicationAuthorizationState(
        basis_digest=basis.digest,
        target_repository=basis.target_repository,
        expected_producer_id=expected_producer_id,
        lifecycle=lifecycle,
    )


def verify_publication_artifacts(
    basis: ReleasePublicationBasis,
    root: Path,
) -> tuple[tuple[str, str], ...]:
    """Re-hash the exact publish directory and reject missing, changed, or extra files."""
    base = root.expanduser().resolve(strict=True)
    if not base.is_dir():
        raise ValueError("publication artifact root must be a directory")
    actual_files: dict[str, Path] = {}
    for path in base.iterdir():
        if path.is_symlink() or not path.is_file():
            raise ValueError(
                "publication artifact root must contain regular files only"
            )
        actual_files[path.name] = path
    expected_names = {item.name for item in basis.artifacts}
    if set(actual_files) != expected_names:
        raise ValueError(
            "publication artifact directory does not match the authorized basis"
        )
    verified: list[tuple[str, str]] = []
    for artifact in sorted(basis.artifacts, key=lambda item: item.name):
        path = actual_files[artifact.name]
        data = path.read_bytes()
        digest = sha256(data).hexdigest()
        if digest != artifact.sha256 or len(data) != artifact.size_bytes:
            raise ValueError(
                f"publication artifact changed after authorization: {artifact.name}"
            )
        verified.append((artifact.name, digest))
    return tuple(verified)


def issue_publication_execution_permit(
    store: WorkspaceHumanApprovalStore,
    basis: ReleasePublicationBasis,
    *,
    artifact_root: Path,
    expected_producer_id: str,
    verification_evidence_path: Path | None = None,
    now: datetime | None = None,
) -> PublicationExecutionPermit:
    """Issue a fresh permit only after revalidating bytes and active authorization."""
    artifacts = verify_publication_artifacts(basis, artifact_root)
    if verification_evidence_path is not None:
        evidence_path = verification_evidence_path.expanduser().resolve(strict=True)
        if not evidence_path.is_file() or evidence_path.is_symlink():
            raise ValueError("publication verification evidence must be a regular file")
        observed = sha256(evidence_path.read_bytes()).hexdigest()
        if observed != basis.verification_evidence_sha256:
            raise ValueError(
                "publication verification evidence changed after authorization"
            )
    state = resolve_publication_authorization(
        store, basis, expected_producer_id=expected_producer_id
    )
    active = state.active
    if not active:
        raise PermissionError("no active canonical publication authorization exists")
    issued_at = now or datetime.now(UTC)
    if issued_at.tzinfo is None:
        raise ValueError("publication permit clock must be timezone-aware")
    return PublicationExecutionPermit(
        basis_digest=basis.digest,
        target_repository=basis.target_repository,
        source_revision=basis.source_revision,
        artifact_sha256=artifacts,
        authorization_receipt_ids=tuple(item.receipt.receipt_id for item in active),
        authorization_receipt_digests=tuple(item.receipt.digest for item in active),
        issued_at=issued_at.astimezone(UTC),
    )


__all__ = [
    "PUBLICATION_ACTION",
    "PUBLICATION_PROFILE_ID",
    "PUBLICATION_PROFILE_VERSION",
    "PublicationAuthorizationState",
    "PublicationExecutionPermit",
    "PublicationTarget",
    "ReleasePublicationBasis",
    "issue_publication_execution_permit",
    "load_publication_execution_permit",
    "load_release_publication_basis",
    "publication_basis_from_release_trust",
    "publication_scope",
    "record_publication_authorization",
    "resolve_publication_authorization",
    "revoke_publication_authorization",
    "verify_publication_artifacts",
    "write_publication_execution_permit",
    "write_release_publication_basis",
]
