"""Regression tests for Tier 13 data lifecycle and confidentiality contracts."""

from __future__ import annotations

import io
import json
import unittest
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

from statewake.adapters.content_store import ContentAddressedArtifactStore
from statewake.adapters.opentelemetry import OpenTelemetryTelemetrySink
from statewake.adapters.retention import InMemoryEvidenceRetentionAdapter
from statewake.domain.access_control import (
    AuthorizationGrant,
    AuthorizationOperation,
    AuthorizationPolicy,
    AuthorizationRequest,
    Principal,
    PrincipalStatus,
)
from statewake.domain.data_lifecycle import (
    DataLifecyclePolicy,
    assess_data_lifecycle,
    build_deletion_record,
    inherit_sensitivity,
)
from statewake.domain.events import EventEnvelope
from statewake.domain.operations import OperationalArtifact, OperationalBundle
from statewake.domain.privacy import PrivacyPolicy
from statewake.domain.retention import EvidenceRetentionRequirement
from statewake.server import VerificationServiceConfig, create_application
from statewake.services.operations_service import export_disclosed_bundle


class _FakeSpan:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, str]]] = []
        self.attributes: dict[str, str] = {}
        self.ended = False

    def add_event(
        self, name: str, *, attributes: dict[str, str], timestamp: int
    ) -> None:
        self.events.append((name, dict(attributes)))

    def set_status(self, value: object) -> None:
        self.status = value

    def end(self, *, end_time: int | None = None) -> None:
        self.ended = True


class _FakeTracer:
    def __init__(self) -> None:
        self.spans: list[_FakeSpan] = []

    def start_span(
        self, name: str, *, attributes: dict[str, str], start_time: int
    ) -> _FakeSpan:
        span = _FakeSpan()
        span.attributes = dict(attributes)
        self.spans.append(span)
        return span


class DataLifecycleConfidentialityTests(unittest.TestCase):
    """Exercise Tier 13 lifecycle and confidentiality invariants."""

    def test_derived_sensitivity_cannot_downgrade_without_approval(self) -> None:
        """Prevent an unapproved reduction in classification."""
        with self.assertRaises(ValueError):
            inherit_sensitivity(("restricted",), requested_sensitivity="internal")
        self.assertEqual(
            inherit_sensitivity(
                ("restricted",),
                requested_sensitivity="internal",
                downgrade_approved=True,
            ),
            "internal",
        )

    def test_lifecycle_retention_and_legal_hold(self) -> None:
        """Require expiry before deletion and keep legal holds authoritative."""
        created = datetime(2026, 1, 1, tzinfo=UTC)
        policy = DataLifecyclePolicy(
            policy_id="p1", purpose="reliability-proof", max_retention_days=30
        )
        expired = assess_data_lifecycle(
            "a",
            sensitivity="internal",
            created_at=created,
            policy=policy,
            now=created + timedelta(days=31),
        )
        self.assertTrue(expired.expired)
        self.assertTrue(expired.deletion_allowed)
        held = assess_data_lifecycle(
            "a",
            sensitivity="internal",
            created_at=created,
            policy=policy,
            now=created + timedelta(days=31),
            legal_hold=True,
        )
        self.assertFalse(held.deletion_allowed)

    def test_deletion_record_preserves_history_without_payload(self) -> None:
        """Preserve identity, digest and reason without retaining deleted bytes."""
        record = build_deletion_record(
            "artifact-1",
            digest="a" * 64,
            sensitivity="restricted",
            deleted_at=datetime(2026, 9, 16, tzinfo=UTC),
            policy_id="ret-1",
            reason="retention expired",
            derived_from=("source-1",),
        )
        payload = record.to_dict()
        self.assertEqual(payload["digest"], "a" * 64)
        self.assertNotIn("content", payload)
        self.assertEqual(payload["derived_from"], ["source-1"])

    def test_disclosure_ceiling_blocks_sensitive_objects(self) -> None:
        """Block restricted data from an internal-only disclosure boundary."""
        decision = assess_data_lifecycle(
            "proof-1",
            sensitivity="restricted",
            created_at=datetime(2026, 9, 1, tzinfo=UTC),
            policy=DataLifecyclePolicy(
                policy_id="p1",
                purpose="share-proof",
                disclosure_max_sensitivity="internal",
            ),
            now=datetime(2026, 9, 16, tzinfo=UTC),
        )
        self.assertFalse(decision.disclosure_allowed)

    def test_encryption_and_tls_requirements_are_explicit(self) -> None:
        """Keep deployment confidentiality requirements declarative."""
        policy = DataLifecyclePolicy(
            policy_id="p1",
            purpose="sensitive-evidence",
            encryption_at_rest_required=True,
            tls_required=True,
        )
        self.assertTrue(policy.encryption_at_rest_required)
        self.assertTrue(policy.tls_required)

    def test_telemetry_does_not_expose_restricted_evidence(self) -> None:
        """Ensure the telemetry boundary excludes restricted metadata."""
        tracer = _FakeTracer()
        sink = OpenTelemetryTelemetrySink(
            tracer,
            privacy_policy=PrivacyPolicy(policy_id="privacy"),
        )
        sink.emit(
            EventEnvelope(
                "run-1",
                0,
                datetime(2026, 9, 16, tzinfo=UTC),
                "run.started",
                "actor",
                name="agent",
                metadata={"authorization": "secret", "public": "ok"},
            )
        )
        self.assertNotIn("secret", json.dumps(tracer.spans[0].attributes))
        self.assertNotIn("secret", json.dumps(tracer.spans[0].events))
        sink.close()

    def test_http_errors_do_not_echo_untrusted_payload(self) -> None:
        """Keep malformed-request errors generic rather than reflective."""
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            application = create_application(
                VerificationServiceConfig(
                    artifact_roots=(root,), allow_insecure_http=True
                )
            )
            captured: dict[str, object] = {}

            def start_response(
                status: str,
                headers: list[tuple[str, str]],
                exc_info: object | None = None,
            ) -> Callable[[bytes], object]:
                del exc_info
                captured["status"] = status
                captured["headers"] = headers
                return lambda _body: None

            response = application(
                {
                    "REQUEST_METHOD": "POST",
                    "PATH_INFO": "/v1/evidence/verify",
                    "wsgi.url_scheme": "http",
                    "CONTENT_LENGTH": "18",
                    "wsgi.input": io.BytesIO(b'{"secret":"DO_NOT_ECHO"'),
                },
                start_response,
            )
            body = b"".join(response).decode("utf-8")
            self.assertEqual(captured["status"], "400 Bad Request")
            self.assertNotIn("DO_NOT_ECHO", body)

    def test_operational_bundle_rejects_sensitivity_downgrade(self) -> None:
        """Reject a derived operational artifact that is less sensitive than its source."""
        source = OperationalArtifact(
            artifact_id="source",
            path="source.txt",
            kind="text",
            sha256="a" * 64,
            size_bytes=1,
            sensitivity="restricted",
        )
        derived = OperationalArtifact(
            artifact_id="derived",
            path="derived.txt",
            kind="text",
            sha256="b" * 64,
            size_bytes=1,
            sensitivity="internal",
            derived_from=("source",),
        )
        with self.assertRaises(ValueError, msg="sensitivity"):
            OperationalBundle(
                bundle_id="bundle",
                manifest_id="manifest",
                agent_name="agent",
                engine_version="0.1.0",
                created_at=datetime(2026, 9, 16, tzinfo=UTC),
                artifacts=(source, derived),
            )

    def test_disclosed_bundle_excludes_restricted_artifacts(self) -> None:
        """Export only artifacts within the declared disclosure ceiling."""
        import tempfile
        from hashlib import sha256

        public = b"public"
        restricted = b"secret"
        artifacts = (
            OperationalArtifact(
                artifact_id="public",
                path="public.txt",
                kind="text",
                sha256=sha256(public).hexdigest(),
                size_bytes=len(public),
                sensitivity="internal",
            ),
            OperationalArtifact(
                artifact_id="restricted",
                path="secret.txt",
                kind="text",
                sha256=sha256(restricted).hexdigest(),
                size_bytes=len(restricted),
                sensitivity="restricted",
            ),
        )
        bundle = OperationalBundle(
            bundle_id="pending",
            manifest_id="pending",
            agent_name="agent",
            engine_version="0.1.0",
            created_at=datetime(2026, 9, 16, tzinfo=UTC),
            artifacts=artifacts,
        )
        bundle = OperationalBundle(
            bundle_id=bundle.computed_bundle_id(),
            manifest_id=bundle.computed_manifest_id(),
            agent_name=bundle.agent_name,
            engine_version=bundle.engine_version,
            created_at=bundle.created_at,
            artifacts=bundle.artifacts,
        )
        files = {
            "artifacts/public/public.txt": public,
            "artifacts/restricted/secret.txt": restricted,
        }
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "disclosed.zip"
            disclosed = export_disclosed_bundle(
                bundle, files, output, max_sensitivity="internal"
            )
            self.assertEqual(
                [item.artifact_id for item in disclosed.artifacts], ["public"]
            )
            with ZipFile(output) as archive:
                names = set(archive.namelist())
            self.assertNotIn("artifacts/restricted/secret.txt", names)

    def test_content_store_deletion_requires_expired_retention(self) -> None:
        """Require retention expiry before payload deletion and return a tombstone."""
        import tempfile

        store_time = datetime(2026, 9, 16, tzinfo=UTC)
        with tempfile.TemporaryDirectory() as directory:
            store = ContentAddressedArtifactStore(Path(directory))
            digest = store.put(b"sensitive")
            retention = InMemoryEvidenceRetentionAdapter()
            retention.require_retention(
                EvidenceRetentionRequirement(digest, store_time + timedelta(days=1))
            )
            with self.assertRaises(PermissionError):
                store.delete(digest, retention=retention, now=store_time)
            record = store.delete(
                digest,
                retention=retention,
                now=store_time + timedelta(days=2),
                sensitivity="restricted",
                policy_id="ret-1",
            )
            self.assertFalse(store.exists(digest))
            self.assertEqual(record.digest, digest)
            self.assertNotIn("content", record.to_dict())

    def test_cross_resource_confidentiality_isolation_delegates_to_authorization(
        self,
    ) -> None:
        """Ensure protected data access remains bound to the requested resource domain."""
        principal = Principal(
            principal_id="p1",
            roles=("reader",),
            resource_scopes={"domain-a": ("public-1",)},
            status=PrincipalStatus.ACTIVE,
        )
        policy = AuthorizationPolicy(
            grants=(
                AuthorizationGrant(
                    role="reader",
                    operation=AuthorizationOperation.READ,
                    allowed_states=("verified",),
                ),
            )
        )
        request = AuthorizationRequest(
            operation=AuthorizationOperation.READ,
            resource_domain="domain-b",
            resource_id="secret-1",
            resource_state="verified",
            requested_at=datetime(2026, 9, 16, tzinfo=UTC),
        )
        decision = policy.authorize(principal, request)
        self.assertFalse(decision.allowed)


if __name__ == "__main__":
    unittest.main()
