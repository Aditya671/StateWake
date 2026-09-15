"""Application services for evidence manifests and content."""

from pathlib import Path

from statewake.utils.json_support import load_object

from ..adapters.content_store import ContentAddressedArtifactStore
from ..domain.evidence import EvidenceManifest


def load_manifest(path: Path) -> EvidenceManifest:
    """Load and validate an evidence manifest."""
    payload = load_object(path)
    if not isinstance(payload, dict):
        raise ValueError("Evidence manifest root must be a JSON object.")
    return EvidenceManifest.from_dict(payload)


def store_content(path: Path, content: bytes) -> str:
    """Store evidence content in the canonical content-addressed store."""
    return ContentAddressedArtifactStore(path).put(content)
