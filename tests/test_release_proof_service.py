import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from statewake.adapters.human_approval import WorkspaceHumanApprovalStore
from statewake.adapters.reliability_attestation import (
    JsonlReliabilityOutcomeAttestationStore,
    SignedReliabilityOutcomeBinding,
)
from statewake.cli.main import build_parser
from statewake.domain.attestation_trust import (
    AttestationTrustAnchor,
    SignedAttestationTrustState,
)
from statewake.domain.reliability_evidence import (
    EvidenceReference,
    ReliabilityEvidenceChain,
)
from statewake.domain.reliability_outcome_verification import (
    ReliabilityOutcomeVerificationReport,
)
from statewake.domain.reliability_verification_report import (
    ReliabilityVerificationReport,
)
from statewake.services.release_proof_service import (
    build_release_proof,
    render_verification_report,
)
from statewake.services.reliability_attestation_service import (
    build_reliability_attestation_trust_context,
    create_signed_reliability_outcome_envelope,
    load_reliability_outcome_attestation,
)
from statewake.services.reliability_proof_bundle_service import (
    verify_reliability_proof_bundle,
)
from tests.support.reliability_proof import prepare_reliability_proof_fixture

D = "a" * 64


def ref(kind, identity):
    return EvidenceReference(kind, identity, D, f"{identity}.json")


def chain():
    return ReliabilityEvidenceChain(
        chain_id="c",
        run=ref("run", "r"),
        state=ref("state", "s"),
        evidence=(ref("evidence", "e"),),
        provenance=ref("provenance", "p"),
        integrity=ref("integrity", "i"),
        verification_status="verified",
        reliability_state="reliable",
        reconciliation_state="verified",
        decision="accept",
        decision_rationale=("bounded release",),
    )


class FakeBundle:
    bundle_id = "bundle-1"
    manifest_id = "manifest-1"


class TestReleaseProof(unittest.TestCase):
    def test_report_renders_portable_inspection_artifact(self):
        report = ReliabilityVerificationReport(
            "1",
            "Release evidence complete",
            "accept",
            "release-evidence-complete",
            "1",
            True,
            ("run", "state", "evidence"),
            (),
            ("chain_verified",),
            (),
            ("r", "s"),
            ("bounded",),
            ("Verification does not establish external correctness."),  # type: ignore
            "verified",
            "statewake-0.6.1",
            "2026-01-01T00:00:00+00:00",
        )
        text = render_verification_report(report)
        self.assertIn("# Reliability Verification Report", text)
        self.assertIn("VERIFIED", text)
        self.assertIn(report.digest, text)

    def test_canonical_signed_release_proof_resolves_historical_trust_and_reports_it(
        self,
    ):
        """Propagate canonical signed trust through release proof and human report."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attestation_path, chain_path, history_path = (
                prepare_reliability_proof_fixture(root)
            )
            attestation = load_reliability_outcome_attestation(attestation_path)
            signing_state = SignedAttestationTrustState(
                authority_key_id="authority-1",
                version=1,
                issued_at="2026-10-01T00:00:00+00:00",
                anchors=(
                    AttestationTrustAnchor("rel-key", b"K" * 32, status="active"),
                ),
                signature="authority-signature-v1",
            )
            current_state = SignedAttestationTrustState(
                authority_key_id="authority-1",
                version=2,
                issued_at="2026-10-02T00:00:00+00:00",
                anchors=(
                    AttestationTrustAnchor("rel-key", b"K" * 32, status="revoked"),
                ),
                signature="authority-signature-v2",
                previous_digest=signing_state.digest(),
            )
            trust_history_path = root / "attestation-trust-history.jsonl"
            trust_history_path.write_text(
                json.dumps(signing_state.to_dict())
                + "\n"
                + json.dumps(current_state.to_dict())
                + "\n",
                encoding="utf-8",
            )
            current_state_path = root / "attestation-trust-state.json"
            current_state_path.write_text(
                json.dumps(current_state.to_dict()), encoding="utf-8"
            )
            authority_path = root / "attestation-authority.json"
            authority_path.write_text(
                json.dumps(
                    {
                        "keys": {
                            "authority-1": base64.urlsafe_b64encode(b"A" * 32)
                            .rstrip(b"=")
                            .decode("ascii")
                        }
                    }
                ),
                encoding="utf-8",
            )
            store_path = root / "attestations.jsonl"
            output = root / "release-proof.zip"
            report_path = root / "release-report.json"
            with (
                patch(
                    "statewake.services.trust_service.Ed25519AttestationTrustStateVerifier.verify",
                    lambda self, state: state,
                ),
                patch(
                    "statewake.services.reliability_attestation_service.Ed25519AttestationTrustStateVerifier.verify",
                    lambda self, state: state,
                ),
                patch(
                    "statewake.services.reliability_attestation_service.verify_ed25519_signature",
                    lambda public_key, message, signature: None,
                ),
            ):
                envelope = create_signed_reliability_outcome_envelope(
                    attestation, key_id="rel-key", signature=b"S" * 64
                )
                context = build_reliability_attestation_trust_context(
                    envelope,
                    trust_state=signing_state,
                    authority_store={"authority-1": b"A" * 32},
                )
                JsonlReliabilityOutcomeAttestationStore(store_path).append_signed(
                    SignedReliabilityOutcomeBinding(envelope, context)
                )
                bundle, report, evaluation = build_release_proof(
                    attestation_path=attestation_path,
                    evidence_chain_path=chain_path,
                    history_path=history_path,
                    evidence_root=root,
                    output=output,
                    report_path=report_path,
                    attestation_store_path=store_path,
                    attestation_trust_state_path=current_state_path,
                    attestation_trust_history_path=trust_history_path,
                    attestation_authority_store_path=authority_path,
                )
                offline, descriptor = verify_reliability_proof_bundle(output)
            self.assertTrue(evaluation.satisfied)
            self.assertTrue(report.verified)
            self.assertTrue(offline.verified)
            self.assertEqual(bundle.bundle_id, bundle.computed_bundle_id())
            self.assertIn("signed_attestation_trust_verified", report.checks_passed)
            self.assertIn(
                "historical_signing_trust_state_resolved", report.checks_passed
            )
            self.assertIn("signed_attestation_trust_context", report.evidence_included)
            self.assertIn(
                "signed_attestation_trust_context", report.machine_readable_appendix
            )
            self.assertIsNotNone(descriptor.attestation_trust_context)
            assert descriptor.attestation_trust_context is not None
            self.assertEqual(
                descriptor.attestation_trust_context.trust_state_version, 1
            )
            self.assertTrue(report_path.is_file())
            self.assertTrue(report_path.with_suffix(".md").is_file())

    def test_release_proof_cli_accepts_canonical_signed_trust_inputs(self):
        """Expose the canonical signed-trust boundary on the existing release command."""
        args = build_parser().parse_args(
            [
                "release-proof",
                "--attestation",
                "attestation.json",
                "--chain",
                "chain.json",
                "--history",
                "history.jsonl",
                "--evidence-root",
                "evidence",
                "--output",
                "release-proof.zip",
                "--attestation-store",
                "attestations.jsonl",
                "--attestation-trust-history",
                "trust-history.jsonl",
                "--attestation-authority-store",
                "authorities.json",
            ]
        )
        self.assertEqual(args.command, "release-proof")
        self.assertEqual(args.attestation_store, Path("attestations.jsonl"))
        self.assertEqual(args.attestation_trust_history, Path("trust-history.jsonl"))
        self.assertEqual(args.attestation_authority_store, Path("authorities.json"))

    def test_unsigned_release_proof_report_remains_backward_compatible(self):
        """Do not add signed-trust assertions to the legacy unsigned workflow."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attestation_path, chain_path, history_path = (
                prepare_reliability_proof_fixture(root)
            )
            _, report, _ = build_release_proof(
                attestation_path=attestation_path,
                evidence_chain_path=chain_path,
                history_path=history_path,
                evidence_root=root,
                output=root / "release-proof.zip",
            )
            self.assertNotIn("signed_attestation_trust_verified", report.checks_passed)
            self.assertNotIn(
                "signed_attestation_trust_context", report.evidence_included
            )

    def test_release_proof_reconciles_canonical_human_approval_into_new_report(self):
        """Re-evaluate one immutable report basis and emit a new approved report."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attestation_path, chain_path, history_path = (
                prepare_reliability_proof_fixture(root)
            )
            basis_path = root / "release-basis.json"
            _, basis, _ = build_release_proof(
                attestation_path=attestation_path,
                evidence_chain_path=chain_path,
                history_path=history_path,
                evidence_root=root,
                output=root / "basis-proof.zip",
                report_path=basis_path,
            )
            basis_bytes = basis_path.read_bytes()
            record_id = "f" * 64
            approval_workspace = root / "approval-workspace"
            approval, created = WorkspaceHumanApprovalStore(approval_workspace).append(
                target_record_id=record_id,
                candidate_identity=basis.candidate_identity,
                candidate_digest=basis.candidate_digest,
                report_digest=basis.digest,
                profile_id=basis.profile_id,
                profile_version=basis.profile_version,
                actor_identity_ref="reviewer:alice",
                actor_role="release-reviewer",
                producer_id="statewake.review-api",
                run_id="run-approval-1",
                approval_action="approve-release-evidence",
                scope="candidate release evidence",
                reason="Reviewed the exact immutable release report.",
                idempotency_key="approval-1",
            )
            self.assertTrue(created)

            approved_path = root / "release-approved.json"
            _, approved, _ = build_release_proof(
                attestation_path=attestation_path,
                evidence_chain_path=chain_path,
                history_path=history_path,
                evidence_root=root,
                output=root / "approved-proof.zip",
                report_path=approved_path,
                approval_basis_report_path=basis_path,
                approval_workspace_path=approval_workspace,
                approval_record_id=record_id,
                approval_producer_id="statewake.review-api",
                approval_action="approve-release-evidence",
                approval_scope="candidate release evidence",
            )

            self.assertEqual(basis_path.read_bytes(), basis_bytes)
            self.assertEqual(basis.approval_status, "requires-human-approval")
            self.assertEqual(approved.approval_status, "approved")
            self.assertIn("human_approval_contract", approved.evidence_included)
            self.assertIn(
                "human_approval_basis_report_verified", approved.checks_passed
            )
            self.assertIn(
                "human_approval_machine_basis_revalidated", approved.checks_passed
            )
            self.assertIn(
                "human_approval_contract_integrity_verified", approved.checks_passed
            )
            self.assertIn(
                "human_approval_lifecycle_active_verified", approved.checks_passed
            )
            self.assertIn(
                "human_approval_recorded_authority_scope_matched",
                approved.checks_passed,
            )
            self.assertIn(basis.digest, approved.artifact_digests)
            self.assertIn(approval.receipt.digest, approved.artifact_digests)
            self.assertIn(approval.receipt.artifact_digest, approved.artifact_digests)
            self.assertTrue(approved_path.is_file())
            self.assertTrue(approved_path.with_suffix(".md").is_file())
            serialized = json.dumps(approved.to_dict(), sort_keys=True)
            self.assertNotIn("reviewer:alice", serialized)
            self.assertNotIn("Reviewed the exact immutable release report.", serialized)

    def test_release_proof_rejects_revoked_human_approval(
        self,
    ):
        """A later revocation must prevent fresh approval reconciliation."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attestation_path, chain_path, history_path = (
                prepare_reliability_proof_fixture(root)
            )
            basis_path = root / "release-basis.json"
            _, basis, _ = build_release_proof(
                attestation_path=attestation_path,
                evidence_chain_path=chain_path,
                history_path=history_path,
                evidence_root=root,
                output=root / "basis-proof.zip",
                report_path=basis_path,
            )
            record_id = "9" * 64
            approval_workspace = root / "approval-workspace"
            store = WorkspaceHumanApprovalStore(approval_workspace)
            approval, _ = store.append(
                target_record_id=record_id,
                candidate_identity=basis.candidate_identity,
                candidate_digest=basis.candidate_digest,
                report_digest=basis.digest,
                profile_id=basis.profile_id,
                profile_version=basis.profile_version,
                actor_identity_ref="reviewer:alice",
                actor_role="release-reviewer",
                producer_id="statewake.review-api",
                run_id="run-approval-1",
                approval_action="approve-release-evidence",
                scope="candidate release evidence",
                reason="Initial approval.",
                idempotency_key="approval-1",
            )
            store.revoke(
                target_record_id=record_id,
                target_approval_receipt_id=approval.receipt.receipt_id,
                candidate_identity=basis.candidate_identity,
                candidate_digest=basis.candidate_digest,
                report_digest=basis.digest,
                profile_id=basis.profile_id,
                profile_version=basis.profile_version,
                actor_identity_ref="reviewer:alice",
                actor_role="release-reviewer",
                producer_id="statewake.review-api",
                run_id="run-approval-1",
                approval_action="approve-release-evidence",
                scope="candidate release evidence",
                reason="Approval intentionally withdrawn.",
                idempotency_key="revocation-1",
            )

            with self.assertRaisesRegex(
                ValueError, "no active canonical human approval"
            ):
                build_release_proof(
                    attestation_path=attestation_path,
                    evidence_chain_path=chain_path,
                    history_path=history_path,
                    evidence_root=root,
                    output=root / "approved-proof.zip",
                    report_path=root / "approved.json",
                    approval_basis_report_path=basis_path,
                    approval_workspace_path=approval_workspace,
                    approval_record_id=record_id,
                    approval_producer_id="statewake.review-api",
                    approval_action="approve-release-evidence",
                    approval_scope="candidate release evidence",
                )

    def test_release_proof_uses_active_superseding_approval_not_predecessor(
        self,
    ):
        """Only the active replacement approval may satisfy fresh reconciliation."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attestation_path, chain_path, history_path = (
                prepare_reliability_proof_fixture(root)
            )
            basis_path = root / "release-basis.json"
            _, basis, _ = build_release_proof(
                attestation_path=attestation_path,
                evidence_chain_path=chain_path,
                history_path=history_path,
                evidence_root=root,
                output=root / "basis-proof.zip",
                report_path=basis_path,
            )
            record_id = "8" * 64
            approval_workspace = root / "approval-workspace"
            store = WorkspaceHumanApprovalStore(approval_workspace)
            first, _ = store.append(
                target_record_id=record_id,
                candidate_identity=basis.candidate_identity,
                candidate_digest=basis.candidate_digest,
                report_digest=basis.digest,
                profile_id=basis.profile_id,
                profile_version=basis.profile_version,
                actor_identity_ref="reviewer:alice",
                actor_role="release-reviewer",
                producer_id="statewake.review-api",
                run_id="run-approval-1",
                approval_action="approve-release-evidence",
                scope="candidate release evidence",
                reason="Initial approval.",
                idempotency_key="approval-1",
            )
            replacement, _ = store.append(
                target_record_id=record_id,
                candidate_identity=basis.candidate_identity,
                candidate_digest=basis.candidate_digest,
                report_digest=basis.digest,
                profile_id=basis.profile_id,
                profile_version=basis.profile_version,
                actor_identity_ref="reviewer:alice",
                actor_role="release-reviewer",
                producer_id="statewake.review-api",
                run_id="run-approval-1",
                approval_action="approve-release-evidence",
                scope="candidate release evidence",
                reason="Corrected approval rationale.",
                idempotency_key="approval-2",
                supersedes_approval_receipt_id=first.receipt.receipt_id,
            )

            _, approved, _ = build_release_proof(
                attestation_path=attestation_path,
                evidence_chain_path=chain_path,
                history_path=history_path,
                evidence_root=root,
                output=root / "approved-proof.zip",
                report_path=root / "approved.json",
                approval_basis_report_path=basis_path,
                approval_workspace_path=approval_workspace,
                approval_record_id=record_id,
                approval_producer_id="statewake.review-api",
                approval_action="approve-release-evidence",
                approval_scope="candidate release evidence",
            )

            self.assertEqual(approved.approval_status, "approved")
            self.assertIn(
                "human_approval_lifecycle_active_verified", approved.checks_passed
            )
            self.assertIn(replacement.receipt.digest, approved.artifact_digests)
            self.assertNotIn(first.receipt.digest, approved.artifact_digests)
            self.assertIn(
                f"human-approval-receipt:{replacement.receipt.receipt_id}",
                approved.source_identities,
            )
            self.assertNotIn(
                f"human-approval-receipt:{first.receipt.receipt_id}",
                approved.source_identities,
            )

    def test_release_proof_approval_reconciliation_fails_closed_on_authority_mismatch(
        self,
    ):
        """Do not count approval evidence from an unexpected producer/action/scope."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attestation_path, chain_path, history_path = (
                prepare_reliability_proof_fixture(root)
            )
            basis_path = root / "release-basis.json"
            _, basis, _ = build_release_proof(
                attestation_path=attestation_path,
                evidence_chain_path=chain_path,
                history_path=history_path,
                evidence_root=root,
                output=root / "basis-proof.zip",
                report_path=basis_path,
            )
            record_id = "e" * 64
            approval_workspace = root / "approval-workspace"
            WorkspaceHumanApprovalStore(approval_workspace).append(
                target_record_id=record_id,
                candidate_identity=basis.candidate_identity,
                candidate_digest=basis.candidate_digest,
                report_digest=basis.digest,
                profile_id=basis.profile_id,
                profile_version=basis.profile_version,
                actor_identity_ref="reviewer:alice",
                actor_role="release-reviewer",
                producer_id="statewake.review-api",
                run_id="run-approval-1",
                approval_action="approve-release-evidence",
                scope="candidate release evidence",
                reason="Reviewed exact basis.",
                idempotency_key="approval-1",
            )
            with self.assertRaisesRegex(
                ValueError, "expected producer, action, and scope"
            ):
                build_release_proof(
                    attestation_path=attestation_path,
                    evidence_chain_path=chain_path,
                    history_path=history_path,
                    evidence_root=root,
                    output=root / "approved-proof.zip",
                    report_path=root / "approved.json",
                    approval_basis_report_path=basis_path,
                    approval_workspace_path=approval_workspace,
                    approval_record_id=record_id,
                    approval_producer_id="statewake.review-api",
                    approval_action="publish-release",
                    approval_scope="candidate release evidence",
                )

    def test_release_proof_approval_reconciliation_rejects_mismatched_candidate_metadata(
        self,
    ):
        """Reject a canonical approval whose stored candidate metadata is stale."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attestation_path, chain_path, history_path = (
                prepare_reliability_proof_fixture(root)
            )
            basis_path = root / "release-basis.json"
            _, basis, _ = build_release_proof(
                attestation_path=attestation_path,
                evidence_chain_path=chain_path,
                history_path=history_path,
                evidence_root=root,
                output=root / "basis-proof.zip",
                report_path=basis_path,
            )
            record_id = "c" * 64
            approval_workspace = root / "approval-workspace"
            WorkspaceHumanApprovalStore(approval_workspace).append(
                target_record_id=record_id,
                candidate_identity=basis.candidate_identity,
                candidate_digest="0" * 64,
                report_digest=basis.digest,
                profile_id=basis.profile_id,
                profile_version=basis.profile_version,
                actor_identity_ref="reviewer:alice",
                actor_role="release-reviewer",
                producer_id="statewake.review-api",
                run_id="run-approval-1",
                approval_action="approve-release-evidence",
                scope="candidate release evidence",
                reason="Reviewed stale candidate metadata.",
                idempotency_key="approval-1",
            )
            with self.assertRaisesRegex(
                ValueError, "metadata does not match the approved report basis"
            ):
                build_release_proof(
                    attestation_path=attestation_path,
                    evidence_chain_path=chain_path,
                    history_path=history_path,
                    evidence_root=root,
                    output=root / "approved-proof.zip",
                    report_path=root / "approved.json",
                    approval_basis_report_path=basis_path,
                    approval_workspace_path=approval_workspace,
                    approval_record_id=record_id,
                    approval_producer_id="statewake.review-api",
                    approval_action="approve-release-evidence",
                    approval_scope="candidate release evidence",
                )

    def test_release_proof_approval_reconciliation_rejects_changed_machine_basis(self):
        """A valid approval cannot be replayed onto a changed verification-report basis."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            attestation_path, chain_path, history_path = (
                prepare_reliability_proof_fixture(root)
            )
            basis_path = root / "release-basis.json"
            _, basis, _ = build_release_proof(
                attestation_path=attestation_path,
                evidence_chain_path=chain_path,
                history_path=history_path,
                evidence_root=root,
                output=root / "basis-proof.zip",
                report_path=basis_path,
            )
            changed = ReliabilityVerificationReport(
                **{
                    **basis.payload(),
                    "caveats": (*basis.caveats, "Changed machine-verification basis."),
                }
            )
            basis_path.write_text(
                json.dumps(changed.to_dict(), sort_keys=True), encoding="utf-8"
            )
            record_id = "d" * 64
            approval_workspace = root / "approval-workspace"
            WorkspaceHumanApprovalStore(approval_workspace).append(
                target_record_id=record_id,
                candidate_identity=changed.candidate_identity,
                candidate_digest=changed.candidate_digest,
                report_digest=changed.digest,
                profile_id=changed.profile_id,
                profile_version=changed.profile_version,
                actor_identity_ref="reviewer:alice",
                actor_role="release-reviewer",
                producer_id="statewake.review-api",
                run_id="run-approval-1",
                approval_action="approve-release-evidence",
                scope="candidate release evidence",
                reason="Reviewed changed basis.",
                idempotency_key="approval-1",
            )
            with self.assertRaisesRegex(
                ValueError, "no longer matches the approved report basis"
            ):
                build_release_proof(
                    attestation_path=attestation_path,
                    evidence_chain_path=chain_path,
                    history_path=history_path,
                    evidence_root=root,
                    output=root / "approved-proof.zip",
                    report_path=root / "approved.json",
                    approval_basis_report_path=basis_path,
                    approval_workspace_path=approval_workspace,
                    approval_record_id=record_id,
                    approval_producer_id="statewake.review-api",
                    approval_action="approve-release-evidence",
                    approval_scope="candidate release evidence",
                )

    def test_release_proof_approval_inputs_are_all_or_nothing_and_preserve_basis_path(
        self,
    ):
        """Reject partial approval configuration and in-place report mutation."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(
                ValueError, "human approval reconciliation requires"
            ):
                build_release_proof(
                    attestation_path=root / "attestation.json",
                    evidence_chain_path=root / "chain.json",
                    history_path=root / "history.jsonl",
                    evidence_root=root,
                    output=root / "proof.zip",
                    approval_basis_report_path=root / "basis.json",
                )
            with self.assertRaisesRegex(ValueError, "must be different paths"):
                build_release_proof(
                    attestation_path=root / "attestation.json",
                    evidence_chain_path=root / "chain.json",
                    history_path=root / "history.jsonl",
                    evidence_root=root,
                    output=root / "proof.zip",
                    report_path=root / "basis.json",
                    approval_basis_report_path=root / "basis.json",
                    approval_workspace_path=root / "workspace",
                    approval_record_id="a" * 64,
                    approval_producer_id="statewake.review-api",
                    approval_action="approve-release-evidence",
                    approval_scope="candidate release evidence",
                )

    def test_release_proof_cli_exposes_human_approval_reconciliation_inputs(self):
        """Expose re-evaluation on the existing release-proof command only."""
        args = build_parser().parse_args(
            [
                "release-proof",
                "--attestation",
                "attestation.json",
                "--chain",
                "chain.json",
                "--history",
                "history.jsonl",
                "--evidence-root",
                "evidence",
                "--output",
                "release-proof.zip",
                "--report",
                "approved.json",
                "--human-approval-basis-report",
                "basis.json",
                "--human-approval-workspace",
                "workspace",
                "--human-approval-record-id",
                "record-1",
                "--human-approval-producer-id",
                "statewake.review-api",
                "--human-approval-action",
                "approve-release-evidence",
                "--human-approval-scope",
                "candidate release evidence",
            ]
        )
        self.assertEqual(args.human_approval_basis_report, Path("basis.json"))
        self.assertEqual(args.human_approval_workspace, Path("workspace"))
        self.assertEqual(args.human_approval_record_id, "record-1")
        self.assertEqual(args.human_approval_action, "approve-release-evidence")

    def test_workflow_verifies_profile_before_emitting_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            chain_path = root / "chain.json"
            chain_path.write_text("{}")
            with (
                patch(
                    "statewake.services.release_proof_service.load_reliability_evidence_chain",
                    return_value=chain(),
                ),
                patch(
                    "statewake.services.release_proof_service.verify_reliability_evidence_chain"
                ),
                patch(
                    "statewake.services.release_proof_service.build_reliability_proof_bundle",
                    return_value=(
                        FakeBundle(),
                        ReliabilityOutcomeVerificationReport(
                            "a", "subject", True, ("attestation_integrity",)
                        ),
                    ),
                ),
            ):
                bundle, report, evaluation = build_release_proof(
                    attestation_path=root / "att.json",
                    evidence_chain_path=chain_path,
                    history_path=root / "history",
                    evidence_root=root,
                    output=root / "proof.zip",
                )
            self.assertEqual(bundle.bundle_id, "bundle-1")  # type: ignore
            self.assertTrue(evaluation.satisfied)
            self.assertTrue(report.verified)


if __name__ == "__main__":
    unittest.main()
