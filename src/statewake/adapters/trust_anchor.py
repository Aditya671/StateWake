"""Filesystem reference implementation for an independently managed trust anchor."""

from __future__ import annotations

import json
from pathlib import Path

from statewake.domain.trust_anchor import (
    AnchorDiscrepancyError,
    TrustAnchor,
    TrustAnchorError,
    TrustCheckpoint,
    TrustCheckpointVerifier,
    ensure_checkpoint_sequence,
)
from statewake.utils.json_support import load_object


class JsonTrustAnchorStore(TrustAnchor):
    """Persist signed checkpoints in a separately managed JSON directory.

    The directory must be operated as an independent trust boundary in deployment;
    placing it on the same privileged storage as the authoritative history does not
    provide deletion protection by itself.
    """

    def __init__(self, root: Path, verifier: TrustCheckpointVerifier) -> None:
        """Initialize the anchor store with its independent storage root."""
        self.root = root
        self.verifier = verifier
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, checkpoint_id: str) -> Path:
        """Return the storage path for a validated checkpoint identifier."""
        if not checkpoint_id or checkpoint_id in {".", ".."}:
            raise TrustAnchorError("checkpoint_id must not be empty or a path segment.")
        if Path(checkpoint_id).name != checkpoint_id:
            raise TrustAnchorError("checkpoint_id must be a single path-safe segment.")
        return self.root / f"{checkpoint_id}.json"

    def publish(self, checkpoint: TrustCheckpoint) -> None:
        """Verify and persist a checkpoint without permitting overwrite."""
        self.verifier.verify(checkpoint)
        path = self._path(checkpoint.checkpoint_id)
        if path.exists():
            existing = self.retrieve(checkpoint.checkpoint_id)
            if (
                existing.digest() == checkpoint.digest()
                and existing.signature == checkpoint.signature
            ):
                return
            raise AnchorDiscrepancyError(
                "checkpoint ID already exists with different content."
            )

        previous = self._latest(subject_id=checkpoint.subject_id)
        ensure_checkpoint_sequence(previous, checkpoint)
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(checkpoint.to_dict(), sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        temporary.replace(path)

    def retrieve(self, checkpoint_id: str) -> TrustCheckpoint:
        """Load and cryptographically verify one checkpoint."""
        payload = load_object(self._path(checkpoint_id), field="trust checkpoint")
        checkpoint = TrustCheckpoint.from_dict(payload)
        if checkpoint.checkpoint_id != checkpoint_id:
            raise TrustAnchorError("checkpoint ID does not match its storage key.")
        return self.verify(checkpoint)

    def verify(self, checkpoint: TrustCheckpoint) -> TrustCheckpoint:
        """Verify a checkpoint through the separately supplied verifier."""
        return self.verifier.verify(checkpoint)

    def latest(self, *, subject_id: str | None = None) -> TrustCheckpoint | None:
        """Return the latest checkpoint for an optional subject."""
        return self._latest(subject_id=subject_id)

    def _latest(self, *, subject_id: str | None = None) -> TrustCheckpoint | None:
        """Load checkpoints for one subject and reject ambiguous latest state."""
        checkpoints: list[TrustCheckpoint] = []
        for path in self.root.glob("*.json"):
            if not path.is_file():
                continue
            checkpoint = self.retrieve(path.stem)
            if subject_id is None or checkpoint.subject_id == subject_id:
                checkpoints.append(checkpoint)
        if not checkpoints:
            return None
        subjects = {item.subject_id for item in checkpoints}
        if subject_id is None and len(subjects) > 1:
            raise AnchorDiscrepancyError(
                "latest checkpoint requires a subject when multiple subjects exist."
            )
        checkpoints.sort(key=lambda item: (item.history_record_count, item.issued_at))
        latest = checkpoints[-1]
        ties = [
            item
            for item in checkpoints
            if item.history_record_count == latest.history_record_count
            and item.issued_at == latest.issued_at
        ]
        if len(ties) > 1:
            raise AnchorDiscrepancyError(
                "independent trust anchor contains ambiguous latest checkpoints."
            )
        for previous, current in zip(checkpoints, checkpoints[1:], strict=False):
            ensure_checkpoint_sequence(previous, current)
        return latest
