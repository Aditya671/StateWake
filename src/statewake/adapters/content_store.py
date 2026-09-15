"""Local content-addressed artifact storage."""

import os
import uuid
from hashlib import sha256
from pathlib import Path


class ContentAddressedArtifactStore:
    """Store opaque bytes under their SHA-256 digest."""

    def __init__(self, root: Path) -> None:
        """Initialize this component with its configured state."""
        self.root = root

    def put(self, content: bytes) -> str:
        """Store content idempotently and return its hexadecimal SHA-256 digest."""
        digest = sha256(content).hexdigest()
        target = self._path_for(digest)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            existing = target.read_bytes()
            actual = sha256(existing).hexdigest()
            if actual != digest:
                raise ValueError(
                    f"Artifact integrity failure: expected {digest}, got {actual}."
                )
            return digest
        temporary = target.with_name(
            f".{target.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        temporary.write_bytes(content)
        try:
            os.link(temporary, target)
        except FileExistsError:
            pass
        finally:
            temporary.unlink(missing_ok=True)
        return digest

    def get(self, digest: str) -> bytes:
        """Retrieve content by digest and verify its integrity."""
        target = self._path_for(digest)
        if not target.exists():
            raise FileNotFoundError(f"Artifact not found: {digest}")
        content = target.read_bytes()
        actual = sha256(content).hexdigest()
        if actual != digest:
            raise ValueError(
                f"Artifact integrity failure: expected {digest}, got {actual}."
            )
        return content

    def exists(self, digest: str) -> bool:
        """Return whether the content address exists."""
        return self._path_for(digest).is_file()

    def _path_for(self, digest: str) -> Path:
        """Return the content-addressed filesystem path for a digest."""
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("digest must be a lowercase SHA-256 hexadecimal string.")
        return self.root / digest[:2] / digest[2:]
