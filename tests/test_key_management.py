import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path

from statewake.adapters.key_management import (
    ExternalCommandSigningProvider,
    ExternalSigningAdapter,
)
from statewake.domain.key_management import SigningKeyReference, public_key_digest


class _Signer:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bytes]] = []

    def sign(self, key: SigningKeyReference, payload: bytes) -> bytes:
        self.calls.append((key.key_id, payload))
        return b"sig"


class _Lifecycle:
    def rotate(self, key):
        return SigningKeyReference("new", "kms")

    def revoke(self, key, *, reason):
        self.reason = reason


class TestKeyManagement(unittest.TestCase):
    def test_external_signing_does_not_accept_private_material(self):
        signer = _Signer()
        lifecycle = _Lifecycle()
        adapter = ExternalSigningAdapter(signer, lifecycle)
        key = SigningKeyReference("old", "kms")
        self.assertEqual(adapter.sign(key, b"payload"), b"sig")
        self.assertEqual(adapter.rotate(key).key_id, "new")
        adapter.revoke(key, reason="scheduled rotation")
        self.assertEqual(lifecycle.reason, "scheduled rotation")

    def test_external_command_signer_uses_bounded_json_protocol(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            request_path = root / "request.json"
            signer = root / "signer.py"
            signer.write_text(
                """
import base64
import json
import pathlib
import sys

request = json.loads(sys.stdin.read())
pathlib.Path(sys.argv[1]).write_text(json.dumps(request), encoding="utf-8")
response = {
    "protocol": "statewake-external-signing.v1",
    "algorithm": request["key"]["algorithm"],
    "key_id": request["key"]["key_id"],
    "signature_base64": base64.urlsafe_b64encode(b"S" * 64).rstrip(b"=").decode("ascii"),
}
print(json.dumps(response))
""".strip()
                + "\n",
                encoding="utf-8",
            )
            key = SigningKeyReference(
                "key-1",
                "test-kms",
                version="7",
                public_key_digest="a" * 64,
            )
            provider = ExternalCommandSigningProvider(
                (sys.executable, str(signer), str(request_path)),
                timeout_seconds=5,
            )
            self.assertEqual(provider.sign(key, b"canonical-payload"), b"S" * 64)
            request = json.loads(request_path.read_text(encoding="utf-8"))
            self.assertEqual(request["protocol"], "statewake-external-signing.v1")
            self.assertEqual(request["key"], key.to_dict())
            self.assertEqual(
                base64.urlsafe_b64decode(request["payload_base64"] + "=="),
                b"canonical-payload",
            )
            self.assertNotIn("private", json.dumps(request).lower())

    def test_external_command_signer_rejects_identity_substitution(self):
        with tempfile.TemporaryDirectory() as directory:
            signer = Path(directory) / "signer.py"
            signer.write_text(
                """
import base64
import json
import sys

request = json.loads(sys.stdin.read())
print(json.dumps({
    "protocol": "statewake-external-signing.v1",
    "algorithm": "Ed25519",
    "key_id": "substituted-key",
    "signature_base64": base64.urlsafe_b64encode(b"S" * 64).rstrip(b"=").decode("ascii"),
}))
""".strip()
                + "\n",
                encoding="utf-8",
            )
            provider = ExternalCommandSigningProvider((sys.executable, str(signer)))
            with self.assertRaisesRegex(ValueError, "key identity mismatch"):
                provider.sign(SigningKeyReference("key-1", "test-kms"), b"payload")

    def test_external_command_signer_does_not_echo_provider_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            signer = Path(directory) / "signer.py"
            signer.write_text(
                """
import sys
print("SYNTHETIC_PROVIDER_SECRET", file=sys.stderr)
raise SystemExit(23)
""".strip()
                + "\n",
                encoding="utf-8",
            )
            provider = ExternalCommandSigningProvider((sys.executable, str(signer)))
            with self.assertRaisesRegex(RuntimeError, "exit code 23") as caught:
                provider.sign(SigningKeyReference("key-1", "test-kms"), b"payload")
            self.assertNotIn("SYNTHETIC_PROVIDER_SECRET", str(caught.exception))

    def test_external_command_signer_rejects_oversized_payload_before_execution(self):
        provider = ExternalCommandSigningProvider(
            (sys.executable, "missing-signer.py"), max_payload_bytes=4
        )
        with self.assertRaisesRegex(ValueError, "payload exceeds size limit"):
            provider.sign(SigningKeyReference("key-1", "test-kms"), b"12345")

    def test_external_command_signer_rejects_wrong_signature_size(self):
        with tempfile.TemporaryDirectory() as directory:
            signer = Path(directory) / "signer.py"
            signer.write_text(
                """
import base64
import json
import sys

request = json.loads(sys.stdin.read())
print(json.dumps({
    "protocol": "statewake-external-signing.v1",
    "algorithm": request["key"]["algorithm"],
    "key_id": request["key"]["key_id"],
    "signature_base64": base64.urlsafe_b64encode(b"S" * 63).rstrip(b"=").decode("ascii"),
}))
""".strip()
                + "\n",
                encoding="utf-8",
            )
            provider = ExternalCommandSigningProvider((sys.executable, str(signer)))
            with self.assertRaisesRegex(ValueError, "exactly 64 bytes"):
                provider.sign(SigningKeyReference("key-1", "test-kms"), b"payload")

    def test_public_key_digest(self):
        self.assertEqual(
            public_key_digest(b"x"),
            "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881",
        )


if __name__ == "__main__":
    unittest.main()
