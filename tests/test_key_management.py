import unittest

from statewake.adapters.key_management import ExternalSigningAdapter
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

    def test_public_key_digest(self):
        self.assertEqual(
            public_key_digest(b"x"),
            "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881",
        )


if __name__ == "__main__":
    unittest.main()
